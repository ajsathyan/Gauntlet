"""Top-level registration order for Gauntlet command families."""


def register_commands(
    subcommands,
    *,
    register_archive,
    register_land,
    register_merge,
    register_review_unit,
    register_closeout,
    register_install,
    register_launch,
    register_docs,
    register_followup_memory,
    register_analytics,
    register_changelog,
    register_diagram,
    command_install_verify,
    command_diagram_find,
):
    register_archive(subcommands)
    register_land(subcommands)
    register_merge(subcommands)
    register_review_unit(subcommands)
    register_closeout(subcommands)
    register_install(subcommands, command=command_install_verify)
    register_launch(subcommands)
    register_docs(subcommands)
    register_followup_memory(subcommands)
    register_analytics(subcommands)
    register_changelog(subcommands)
    register_diagram(subcommands, command=command_diagram_find)
