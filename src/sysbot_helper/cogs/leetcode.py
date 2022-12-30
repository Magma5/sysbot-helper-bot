from datetime import datetime
import traceback
from discord.ext import commands
import aiohttp

from pydantic import BaseModel
from sysbot_helper import scheduled

QUERY_DAILY_CHALLENGE_RECORDS = """
query dailyCodingQuestionRecords($year: Int!, $month: Int!) {
  dailyCodingChallengeV2(year: $year, month: $month) {
    challenges {
      date
      link
      question {
        questionFrontendId
        title
      }
    }
  }
}
"""

QUERY_ACTIVE_DAILY_CHALLENGE = """
query questionOfToday {
  activeDailyCodingChallengeQuestion {
    date
    link
    question {
      difficulty
      questionFrontendId
      title
    }
  }
}
"""


class LeetcodeConfig(BaseModel):
    channels: list[int]
    debug: bool = False


class Leetcode(commands.Cog):
    """Announce leetcode daily challenges."""

    seen_dates = None

    def __init__(self, bot, config: LeetcodeConfig):
        self.bot = bot
        self.config = config

        if config.debug:
            self.seen_dates = set()

    async def fetch_daily_challenges(self):
        request = {
            "query": QUERY_ACTIVE_DAILY_CHALLENGE,
            "variables": {}
        }
        headers = {
            'content-type': 'application/json'
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post('https://leetcode.com/graphql/', json=request) as response:
                if response.ok:
                    response = await response.json()
                    challenge = response['data']['activeDailyCodingChallengeQuestion']
                    date = challenge['date']

                    if self.seen_dates is None:
                        self.seen_dates = set()
                    elif date not in self.seen_dates:
                        await self.announce(challenge)

                    self.seen_dates.add(date)

    async def announce(self, challenge):
        date = challenge['date']
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        weekday = date_obj.strftime('%A')
        link = f"https://leetcode.com{challenge['link']}"
        frontend_id = challenge['question']['questionFrontendId']
        title = challenge['question']['title']
        difficulty = challenge['question']['difficulty']

        for channel in self.config.channels:
            ch = self.bot.get_channel(channel)
            message = await ch.send(f'**LeetCode Daily Challenge**\nDate: {date}\n#{frontend_id}: **[{difficulty}]** {title}\nLink: {link}')
            await message.create_thread(name=f'LeetCode {frontend_id} ({weekday})', auto_archive_duration=1440)

    @scheduled('1-/10 * * * *')
    async def leetcode_update(self):
        try:
            await self.fetch_daily_challenges()
        except Exception:
            traceback.print_exc()
