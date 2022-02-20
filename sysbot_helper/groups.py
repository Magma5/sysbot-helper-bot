class Groups:
    ALL_GROUP = 'all'

    def __init__(self, config):
        self.groups = {}
        self.groups[self.ALL_GROUP] = set()
        self.add_group(config)

    def add_group(self, config):
        members, groups = self.flatten_groups(config)
        self.groups[self.ALL_GROUP].update(members)
        self.groups.update(groups)

    @classmethod
    def flatten_groups(cls, config):
        subgroups = {}
        members = set()

        if isinstance(config, int):
            members.add(config)

        elif isinstance(config, list):
            for v in config:
                members_, subgroups_ = cls.flatten_groups(v)
                members.update(members_)
                subgroups.update(subgroups_)

        elif isinstance(config, dict):
            for k, v in config.items():
                members_, subgroups_ = cls.flatten_groups(v)
                members.update(members_)
                subgroups.update(subgroups_)
                if k in subgroups:
                    subgroups[k].update(members_)
                else:
                    subgroups[k] = members_

        return members, subgroups

    def in_group(self, member_id, name):
        if name not in self.groups:
            return False
        return member_id in self.groups[name]

    def in_group_any(self, member_id, *groups):
        return any(self.in_group(member_id, group) for group in groups)

    def in_group_all(self, member_id, *groups):
        return all(self.in_group(member_id, group) for group in groups)

    def get_members(self, *groups):
        members = set()
        for group in groups:
            if isinstance(group, int):
                members.add(group)
            else:
                members.update(self.groups.get(group, set()))
        return members

    def __repr__(self) -> str:
        return self.groups.__repr__()

    def __str__(self) -> str:
        return self.groups.__str__()
