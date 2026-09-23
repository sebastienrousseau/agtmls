# bash completion for agtmls -*- shell-script -*-
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT

_agtmls_completions() {
    local cur prev words cword
    _init_completion || return

    local subcommands="audit bench bump-version check diff docs-site doctor evidence evolve export import-skill index install list mcp-resources next-version plugin-manifests profiles propose-skill provenance provider-install providers release-check release-dry-run release-pack sbom scaffold-skill search show stats status uninstall verify verify-release-assets"

    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${subcommands}" -- "$cur") )
        return 0
    fi

    case "${words[1]}" in
        install)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "python rust typescript go ruby generic" -- "$cur") )
            elif [[ $cword -eq 3 ]]; then
                COMPREPLY=( $(compgen -W "aider antigravity claude codex" -- "$cur") )
            fi
            ;;
        uninstall)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "aider antigravity claude codex" -- "$cur") )
            fi
            ;;
        audit|show)
            _filedir
            ;;
        *)
            ;;
    esac
}

complete -F _agtmls_completions agtmls
