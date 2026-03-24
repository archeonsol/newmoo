"""
Cmdset for Spirit (death limbo puppet). Only go light / go shard are permitted;
every other command is intercepted and blocked.
"""
from evennia import default_cmds
from commands.command import CmdGoShard, CmdGoLight
from evennia.commands.command import Command


_SPIRIT_BLOCK_MSG = (
    "|xAs a spirit you can only:|n\n"
    "  |wgo light|n  – let go and return to the connection screen\n"
    "  |wgo shard|n  – wake in your clone body (if a shard is stored)"
)


class CmdSpiritNoMatch(Command):
    """Catch-all that blocks every command not explicitly allowed for spirits."""

    key = "CMD_NOMATCH"
    # Fired by Evennia when no other command matches the input.
    aliases = []
    locks = "cmd:all()"
    auto_help = False

    def func(self):
        self.caller.msg(_SPIRIT_BLOCK_MSG)


class CmdSpiritBlock(Command):
    """
    Placeholder that shadows every single-word or multi-word command the
    Account/Character cmdsets would otherwise expose.  We give it a wildcard
    key so Evennia's merger picks it up for any input that *does* match
    something in a lower-priority cmdset.
    """

    key = "CMD_MULTIMATCH"
    aliases = []
    locks = "cmd:all()"
    auto_help = False

    def func(self):
        self.caller.msg(_SPIRIT_BLOCK_MSG)


class SpiritCmdSet(default_cmds.CmdSet):
    """Spirit in Death Lobby: only go light and go shard are allowed."""

    key = "SpiritCmdSet"
    # Higher priority than Account (1) and Character (0) cmdsets so our
    # commands win every merge conflict.
    priority = 10
    # Merge-type REPLACE means this cmdset's commands fully shadow the others
    # instead of being merged alongside them.
    mergetype = "REPLACE"
    # Still allow the two permitted commands added below to be found.
    no_exits = False
    no_objs = False

    def at_cmdset_creation(self):
        self.add(CmdGoShard())
        self.add(CmdGoLight())
        self.add(CmdSpiritNoMatch())
        self.add(CmdSpiritBlock())
