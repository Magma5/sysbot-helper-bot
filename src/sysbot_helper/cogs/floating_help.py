import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum, auto
from time import time

from discord import HTTPException, NotFound, TextChannel
from discord.ext import commands
from pydantic import BaseModel

from sysbot_helper import Bot, scheduled

log = logging.getLogger(__name__)


class WorkerEventType(Enum):
    MSG_RECEIVED = auto()
    FORCE_REFRESH = auto()
    STOP = auto()


@dataclass
class WorkerEvent:
    event_type: WorkerEventType
    message_text: str = ""
    timestamp: float = field(default_factory=time)


class ChannelWorker:
    """Single-writer worker managing floating help state for a single channel."""

    def __init__(self, channel_id: int, cog: "FloatingHelp"):
        self.channel_id = channel_id
        self.cog = cog
        self.queue: asyncio.Queue[WorkerEvent] = asyncio.Queue()
        self.task: asyncio.Task | None = None
        self.last_activity: float = time()
        self.active_message_id: int | None = None
        self.message_text: str = ""

    def start(self) -> None:
        """Starts the background processing task if not already running."""
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stops the worker loop cleanly."""
        await self.queue.put(WorkerEvent(WorkerEventType.STOP))
        if self.task and not self.task.done():
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    def notify_message(self) -> None:
        """Notifies worker of channel message activity."""
        self.last_activity = time()
        # Coalesce: put MSG_RECEIVED only if queue is empty or last event isn't MSG_RECEIVED
        self.queue.put_nowait(WorkerEvent(WorkerEventType.MSG_RECEIVED))

    def notify_force_refresh(self, message_text: str) -> None:
        """Requests an immediate or scheduled refresh with updated template text."""
        self.message_text = message_text
        self.queue.put_nowait(WorkerEvent(WorkerEventType.FORCE_REFRESH, message_text=message_text))

    async def _run_loop(self) -> None:
        while True:
            try:
                event = await self.queue.get()
                if event.event_type == WorkerEventType.STOP:
                    break

                if event.event_type == WorkerEventType.MSG_RECEIVED:
                    await self._wait_for_quiet_period()

                # Drain redundant MSG_RECEIVED events to collapse activity bursts
                self._drain_queue()

                await self._refresh_message()
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Error in ChannelWorker for channel %s. Backing off.", self.channel_id)
                await asyncio.sleep(5)

    def _drain_queue(self) -> None:
        """Drains extra enqueued activity signals to prevent queue bloat."""
        while not self.queue.empty():
            try:
                event = self.queue.get_nowait()
                if event.event_type == WorkerEventType.STOP:
                    self.queue.put_nowait(event)
                    break
                if event.event_type == WorkerEventType.FORCE_REFRESH and event.message_text:
                    self.message_text = event.message_text
            except asyncio.QueueEmpty:
                break

    async def _wait_for_quiet_period(self) -> None:
        """Waits until channel is idle for channel_activity_wait seconds."""
        quiet_seconds = self.cog.config.channel_activity_wait
        while True:
            elapsed = time() - self.last_activity
            remaining = quiet_seconds - elapsed
            if remaining <= 0:
                break

            try:
                event = await asyncio.wait_for(self.queue.get(), timeout=remaining)
                if event.event_type == WorkerEventType.STOP:
                    self.queue.put_nowait(event)
                    raise asyncio.CancelledError()
                if event.event_type == WorkerEventType.FORCE_REFRESH and event.message_text:
                    self.message_text = event.message_text
            except TimeoutError:
                break

    async def _refresh_message(self) -> None:
        channel = self.cog.bot.get_channel(self.channel_id)
        if not isinstance(channel, TextChannel) or self.cog.should_skip(channel):
            return

        variables = self.cog.bot.template_variables(channel)
        rendered_content = (
            self.cog.bot.template_engine.render_string(self.message_text, variables).strip()
            + self.cog.config.magic_space
        )

        last_msg = None
        async for msg in channel.history(limit=1):
            last_msg = msg

        # Case 1: Floating help is already the latest message in the channel
        if last_msg and (
            last_msg.id == self.active_message_id
            or (last_msg.author == self.cog.bot.user and last_msg.content.endswith(self.cog.config.magic_space))
        ):
            self.active_message_id = last_msg.id
            if last_msg.content == rendered_content:
                return

            try:
                await last_msg.edit(content=rendered_content)
                return
            except NotFound:
                self.active_message_id = None
            except HTTPException as e:
                log.warning("Failed to edit floating help in channel %s: %s", self.channel_id, e)
                return

        # Case 2: Latest message is a user message or floating help missing at bottom
        await self._purge_old_floating_messages(channel)

        try:
            new_msg = await channel.send(rendered_content)
            self.active_message_id = new_msg.id
        except HTTPException as e:
            log.warning("Failed to send floating help message in channel %s: %s", self.channel_id, e)

    async def _purge_old_floating_messages(self, channel: TextChannel) -> None:
        """Purges old floating help messages from history."""
        try:
            async for msg in channel.history(limit=self.cog.config.check_message_history):
                if msg.author == self.cog.bot.user and msg.content.endswith(self.cog.config.magic_space):
                    if msg.id == self.active_message_id:
                        continue
                    with suppress(HTTPException, NotFound):
                        await msg.delete()
        except (HTTPException, NotFound):
            pass


class FloatingHelp(commands.Cog):
    class Config(BaseModel):
        channels: dict[int | str, str]
        check_message_history: int = 50
        channel_activity_wait: int = 30
        magic_space: str = "⠀"
        auto_refresh: bool = True
        auto_refresh_interval: int = 30
        skip_locked_channels: bool = False

    def __init__(self, bot: Bot, config: Config):
        self.bot = bot
        self.config = config
        self.workers: dict[int, ChannelWorker] = {}

    def cog_unload(self) -> None:
        """Cancels active worker tasks upon cog unregistration."""
        for worker in list(self.workers.values()):
            if worker.task and not worker.task.done():
                worker.task.cancel()
        self.workers.clear()

    def should_skip(self, channel: TextChannel) -> bool:
        if getattr(channel, "guild", None) is None:
            return True
        perms = channel.permissions_for(channel.guild.default_role)
        return self.config.skip_locked_channels and perms.send_messages is False

    @scheduled("*/10 * * * * *", on_ready=True, single_instance=True)
    async def auto_refresh(self) -> None:
        """Periodic auto-refresh tick discovering channels and routing worker notifications."""
        active_channel_ids = set()
        for name, message_text in self.config.channels.items():
            for channel in self.bot.get_channels_in_group(name):
                active_channel_ids.add(channel.id)
                if channel.id not in self.workers:
                    self.workers[channel.id] = ChannelWorker(channel.id, self)
                    self.workers[channel.id].start()
                self.workers[channel.id].notify_force_refresh(message_text)

        # Clean up workers for channels that were removed from config
        stale_ids = set(self.workers.keys()) - active_channel_ids
        for channel_id in stale_ids:
            worker = self.workers.pop(channel_id, None)
            if worker:
                await worker.stop()

    @commands.Cog.listener("on_message")
    async def on_message(self, message) -> None:
        if message.author == self.bot.user or message.content.endswith(self.config.magic_space):
            return

        worker = self.workers.get(message.channel.id)
        if worker:
            worker.notify_message()
