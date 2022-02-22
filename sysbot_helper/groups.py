import json
from os.path import exists
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any
from itertools import chain


@dataclass
class Group:
    members: set[Any] = field(default_factory=set)
    childs: set[int] = field(default_factory=set)


def serialize_sets(obj):
    if isinstance(obj, set):
        return list(obj)
    return obj


class Groups:
    ALL_GROUP = 'all'

    def __init__(self, config={}, save_file=None):
        self.group_names = {}
        self.groups = []
        self.update(config)
        self.init_save_file(save_file)

    def init_save_file(self, fn):
        self.saved_groups = defaultdict(set)

        if fn and exists(fn):
            with open(fn) as f:
                saved_groups = json.load(f)
                for name, members in saved_groups.items():
                    self.add_member_save(name, *members)
            self.save_file = fn

    def write_save_file(self):
        if getattr(self, 'save_file', None):
            with open(self.save_file, 'w') as f:
                json.dump(self.saved_groups, f, indent=2, default=serialize_sets)

    def add_member_save(self, name, *member_ids):
        if name not in self.saved_groups:
            group = self.ensure_group(name)
            group.childs.add(len(self.groups))
            self.groups.append(Group(self.saved_groups[name]))
        self.saved_groups[name].update(member_ids)
        self.write_save_file()

    def remove_member_save(self, name, *member_ids):
        self.saved_groups[name].difference_update(member_ids)
        self.write_save_file()

    def update(self, config):
        self._update_groups(self.ALL_GROUP, config)

    def in_group(self, member_id, name):
        return self.in_group_any(member_id, name)

    def in_group_any(self, member_id, *groups):
        return member_id in self.get_members(*groups)

    def in_group_all(self, member_id, *groups):
        return all(self.in_group(member_id, group) for group in groups)

    def get_members(self, *groups, member_types=(int,)):
        # BFS
        q = deque()
        members = set()
        for name in groups:
            if name in self.group_names:
                q.append(self.group_names[name])
            elif isinstance(name, member_types):
                members.add(name)
        visited = set(q)

        while q:
            group = q.popleft()
            members.update(self.groups[group].members)
            for child in self.groups[group].childs:
                if child in visited:
                    continue
                q.append(child)
                visited.add(child)

        return members

    def get_all_members(self):
        return set(chain(*(g.members for g in self.groups)))

    def get_group(self, name):
        return self.groups[self.group_names[name]]

    def ensure_group(self, name):
        if name not in self.group_names:
            self.group_names[name] = len(self.groups)
            self.groups.append(Group())
        return self.get_group(name)

    def _update_groups(self, name, value):
        group = self.ensure_group(name)

        if isinstance(value, list):
            for v in value:
                self._update_groups(name, v)
        elif isinstance(value, dict):
            for k, v in value.items():
                self._update_groups(k, v)
                group.childs.add(self.group_names[k])
        else:  # actual value
            group.members.add(value)

    def __repr__(self) -> str:
        return repr(self.groups)

    def __str__(self) -> str:
        return str(self.groups)
