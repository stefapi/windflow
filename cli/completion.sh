#!/bin/bash
# Script d'auto-complétion pour WindFlow CLI
# Source ce fichier dans votre ~/.bashrc ou ~/.zshrc

_windflow_completion() {
    local cur prev opts base
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Commandes principales
    local commands="auth config org env deploy"

    # Si on est sur la première commande
    if [ $COMP_CWORD -eq 1 ]; then
        COMPREPLY=( $(compgen -W "${commands} --help --version" -- ${cur}) )
        return 0
    fi

    # Complétion basée sur la commande
    case "${COMP_WORDS[1]}" in
        auth)
            local auth_commands="login logout status"
            if [ $COMP_CWORD -eq 2 ]; then
                COMPREPLY=( $(compgen -W "${auth_commands}" -- ${cur}) )
            else
                case "${COMP_WORDS[2]}" in
                    login)
                        COMPREPLY=( $(compgen -W "--username --password" -- ${cur}) )
                        ;;
                esac
            fi
            ;;

        config)
            local config_commands="set-url get-url show set get"
            if [ $COMP_CWORD -eq 2 ]; then
                COMPREPLY=( $(compgen -W "${config_commands}" -- ${cur}) )
            fi
            ;;

        org)
            local org_commands="list get"
            if [ $COMP_CWORD -eq 2 ]; then
                COMPREPLY=( $(compgen -W "${org_commands}" -- ${cur}) )
            else
                case "${COMP_WORDS[2]}" in
                    list|get)
                        COMPREPLY=( $(compgen -W "--format" -- ${cur}) )
                        ;;
                esac
            fi
            ;;

        env)
            local env_commands="list get create delete"
            if [ $COMP_CWORD -eq 2 ]; then
                COMPREPLY=( $(compgen -W "${env_commands}" -- ${cur}) )
            else
                case "${COMP_WORDS[2]}" in
                    list)
                        COMPREPLY=( $(compgen -W "--org --format" -- ${cur}) )
                        ;;
                    get)
                        COMPREPLY=( $(compgen -W "--format" -- ${cur}) )
                        ;;
                    create)
                        COMPREPLY=( $(compgen -W "--name --org --type" -- ${cur}) )
                        ;;
                    delete)
                        COMPREPLY=( $(compgen -W "--confirm" -- ${cur}) )
                        ;;
                esac
            fi
            ;;

        deploy)
            local deploy_commands="create list status logs"
            if [ $COMP_CWORD -eq 2 ]; then
                COMPREPLY=( $(compgen -W "${deploy_commands}" -- ${cur}) )
            else
                case "${COMP_WORDS[2]}" in
                    create)
                        COMPREPLY=( $(compgen -W "--stack --environment --target --name" -- ${cur}) )
                        ;;
                    list)
                        COMPREPLY=( $(compgen -W "--environment --status --format" -- ${cur}) )
                        ;;
                    status)
                        COMPREPLY=( $(compgen -W "--format" -- ${cur}) )
                        ;;
                    logs)
                        COMPREPLY=( $(compgen -W "--tail --follow" -- ${cur}) )
                        ;;
                esac
            fi
            ;;
    esac

    return 0
}

# Enregistrer la fonction de complétion
complete -F _windflow_completion windflow

# Pour zsh, ajouter aussi :
# autoload -U +X compinit && compinit
# autoload -U +X bashcompinit && bashcompinit
# complete -F _windflow_completion windflow
