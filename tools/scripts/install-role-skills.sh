#!/bin/sh
# Usage: sh install-role-skills.sh SOURCE_BUNDLE_ROOT DESTINATION_SKILLS_DIR [DESTINATION_AGENTS_DIR]
# The destination may be new, but its parent must exist. No implicit targets,
# replacement, or legacy cleanup. Run with exclusive access to both trees.
# Preflight prevents validation/collision partial installs, not I/O failures.
set -eu

fail() { printf '%s\n' "install-role-skills: $*" >&2; exit 1; }

[ "$#" -eq 2 ] || [ "$#" -eq 3 ] || fail "usage: $0 SOURCE_BUNDLE_ROOT DESTINATION_SKILLS_DIR [DESTINATION_AGENTS_DIR]"
[ -n "$1" ] && [ -n "$2" ] || fail 'both paths must be nonempty'
# Prefix relative paths so utilities never interpret them as options.
case $1 in /*) source=$1 ;; *) source=$PWD/$1 ;; esac
case $2 in /*) destination=$2 ;; *) destination=$PWD/$2 ;; esac
source=$(CDPATH= cd "$source" && pwd -P) || fail 'source root must be a directory'
while [ "${destination%/}" != "$destination" ]; do destination=${destination%/}; done
[ -n "$destination" ] || destination=/
if [ -e "$destination" ] || [ -L "$destination" ]; then
    [ -d "$destination" ] || fail "not a destination directory: $destination"
    destination=$(CDPATH= cd "$destination" && pwd -P)
else
    parent=$(CDPATH= cd "$(dirname "$destination")" && pwd -P) ||
        fail 'destination parent must exist'
    destination=$parent/$(basename "$destination")
fi

roles='run-as-orchestrator run-as-designer run-as-planner run-as-implementer run-as-code-reviewer run-as-experimental-reviewer run-as-archivist'
bundles="$roles experimental-development"
agents='orchestrator designer planner implementer code-reviewer experimental-reviewer archivist'
agent_destination=
if [ "$#" -eq 3 ]; then
    [ -n "$3" ] || fail 'agent destination must be nonempty'
    case $3 in /*) agent_destination=$3 ;; *) agent_destination=$PWD/$3 ;; esac
    while [ "${agent_destination%/}" != "$agent_destination" ]; do agent_destination=${agent_destination%/}; done
    [ -n "$agent_destination" ] || fail 'agent destination cannot be filesystem root'
    if [ -e "$agent_destination" ] || [ -L "$agent_destination" ]; then
        [ -d "$agent_destination" ] || fail 'agent destination must be a directory'
        agent_destination=$(CDPATH= cd "$agent_destination" && pwd -P)
        [ -w "$agent_destination" ] && [ -x "$agent_destination" ] || fail 'agent destination is not writable'
    else
        agent_parent=$(CDPATH= cd "$(dirname "$agent_destination")" && pwd -P) || fail 'agent destination parent must exist'
        [ -w "$agent_parent" ] && [ -x "$agent_parent" ] || fail 'agent destination parent is not writable'
        agent_destination=$agent_parent/$(basename "$agent_destination")
    fi
    case $agent_destination/ in "$source/"*|"$destination/"*) fail 'agent destination cannot be inside source or skill destination' ;; esac
    case $destination/ in "$agent_destination/"*) fail 'skill destination cannot be inside agent destination' ;; esac
    for name in $agents; do
        file=$source/adapters/opencode/agents/$name.md
        [ ! -L "$file" ] && [ -f "$file" ] && [ -s "$file" ] && [ -r "$file" ] || fail "missing or unsafe agent: $file"
        target=$agent_destination/$name.md
        if [ -e "$target" ] || [ -L "$target" ]; then
            [ ! -L "$target" ] && [ -f "$target" ] || fail "unsafe agent destination: $target"
            cmp -s "$file" "$target" || fail "agent differs (left unchanged): $target"
        fi
    done
fi

# Subshell recursion keeps each directory's loop variable private (POSIX sh).
# Refuse links and special files rather than exporting external dependencies
# or letting diff follow links outside the selected bundle.
check_tree() (
    [ ! -L "$1" ] || fail "symlink not allowed in bundle: $1"
    if [ -d "$1" ]; then
        [ -r "$1" ] && [ -x "$1" ] || fail "unreadable directory: $1"
        for entry in "$1"/* "$1"/.[!.]* "$1"/..?*; do
            [ -e "$entry" ] || [ -L "$entry" ] || continue
            check_tree "$entry" || exit 1
        done
    else
        [ -f "$1" ] && [ -r "$1" ] || fail "not a readable regular file: $1"
    fi
)

# Complete both preflights before even creating the destination directory.
for name in $bundles; do
    case $name in
        run-as-*) bundle=$source/roles/$name ;;
        *) bundle=$source/flows/$name ;;
    esac
    [ -d "$bundle" ] || fail "missing source bundle: $bundle"
    [ -f "$bundle/SKILL.md" ] && [ -s "$bundle/SKILL.md" ] ||
        fail "bundle requires a nonempty SKILL.md: $bundle"
    check_tree "$bundle"
    case $destination/ in "$bundle/"*) fail 'destination cannot be inside a source bundle' ;; esac
done
for name in $bundles; do
    target=$destination/$name
    if [ -e "$target" ] || [ -L "$target" ]; then
        [ -d "$target" ] || fail "destination collision: $target"
        check_tree "$target"
        diff -r "$bundle" "$target" >/dev/null 2>&1 ||
            fail "destination differs (left unchanged): $target"
    fi
done
if [ -d "$destination" ]; then
    [ -w "$destination" ] && [ -x "$destination" ] || fail 'destination is not writable'
else
    [ -w "$parent" ] && [ -x "$parent" ] || fail 'destination parent is not writable'
fi

mkdir -p "$destination"
for name in $bundles; do
    target=$destination/$name
    if [ -e "$target" ] || [ -L "$target" ]; then
        printf 'unchanged: %s\n' "$name"
    else
        cp -Rp "$bundle" "$target"
        printf 'installed: %s\n' "$name"
    fi
done
if [ -n "$agent_destination" ]; then
    mkdir -p "$agent_destination"
    for name in $agents; do
        if [ ! -e "$agent_destination/$name.md" ]; then
            cp -p "$source/adapters/opencode/agents/$name.md" "$agent_destination/$name.md"
        fi
        printf 'agent: %s\n' "$name"
    done
fi
