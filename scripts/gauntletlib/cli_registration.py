"""Top-level registration order for controller-free Gauntlet commands."""


def register_commands(
    subcommands,
    *,
    register_archive,
    register_land,
    register_merge,
    register_closeout,
    register_install,
    register_docs,
    register_followup,
    register_changelog,
    register_diagram,
    register_workflow,
    command_install_verify,
    command_diagram_find,
):
    register_archive(subcommands)
    register_land(subcommands)
    register_merge(subcommands)
    register_closeout(subcommands)
    register_install(subcommands, command=command_install_verify)
    register_docs(subcommands)
    register_followup(subcommands)
    register_changelog(subcommands)
    register_diagram(subcommands, command=command_diagram_find)
    register_workflow(subcommands)
