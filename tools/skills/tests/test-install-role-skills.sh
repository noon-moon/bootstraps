#!/bin/sh
# Pass an approved existing scratch directory; fixtures never touch live config.
# Usage: sh test-install-role-skills.sh TEMP_PARENT
set -eu
[ "$#" -eq 1 ] && [ -d "$1" ] || { printf 'usage: %s TEMP_PARENT\n' "$0" >&2; exit 1; }
installer=$(CDPATH= cd "$(dirname "$0")/.." && pwd)/install-role-skills.sh
scratch=$(mktemp -d "$1/role skills.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
trap 'exit 1' HUP INT TERM
source=$scratch/source\ bundles
destination=$scratch/export\ skills
names='run-as-orchestrator run-as-designer run-as-planner run-as-implementer run-as-code-reviewer run-as-experimental-reviewer experimental-development'
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
reject() {
    if sh "$installer" "$@" >"$scratch/output" 2>&1; then fail 'expected rejection'; fi
}
for name in $names; do
    mkdir -p "$source/$name/companion files/empty dir"
    printf '%s\n' '---' "name: $name" 'description: Fixture skill.' '---' '# Fixture' >"$source/$name/SKILL.md"
    printf '\000\001companion\377\n' >"$source/$name/companion files/data.bin"
    printf 'hidden\n' >"$source/$name/.hidden"
done
mkdir "$source/not-selected"
printf 'unrelated\n' >"$source/not-selected/SKILL.md"
sh "$installer" "$source" "$destination" >"$scratch/output"
for name in $names; do
    diff -r "$source/$name" "$destination/$name" || fail "incomplete bundle: $name"
done
[ ! -e "$destination/not-selected" ] || fail 'copied unselected bundle'
printf 'PASS: all seven bundles, binary/hidden companions, empty dirs, spaces\n'

mkdir "$destination/legacy-skill"
printf 'leave alone\n' >"$destination/legacy-skill/SKILL.md"
cp -Rp "$destination" "$scratch/snapshot"
sh "$installer" "$source" "$destination" >"$scratch/output"
diff -r "$scratch/snapshot" "$destination" || fail 'rerun changed destination'
printf 'PASS: identical rerun and legacy directory preserved\n'

# Put a collision last in the allowlist, with all earlier bundles absent.
collision=$scratch/collision
mkdir -p "$collision/experimental-development"
printf 'local edit\n' >"$collision/experimental-development/SKILL.md"
cp -Rp "$collision" "$scratch/collision-before"
reject "$source" "$collision"
diff -r "$scratch/collision-before" "$collision" || fail 'partial install on collision'
printf 'PASS: late collision rejected before any installation\n'

last=$source/experimental-development
mv "$last" "$scratch/saved-bundle"
reject "$source" "$scratch/missing-source-target"
[ ! -e "$scratch/missing-source-target" ] || fail 'missing source created target'
mv "$scratch/saved-bundle" "$last"
mv "$last/SKILL.md" "$scratch/saved-skill"
for malformed in missing empty directory; do
    case $malformed in empty) : >"$last/SKILL.md" ;; directory) rm "$last/SKILL.md"; mkdir "$last/SKILL.md" ;; esac
    reject "$source" "$scratch/malformed-target"
    [ ! -e "$scratch/malformed-target" ] || fail 'malformed source created target'
done
rmdir "$last/SKILL.md"
mv "$scratch/saved-skill" "$last/SKILL.md"
printf 'PASS: missing bundle and missing/empty/directory SKILL.md rejected\n'

ln -s "$scratch/saved-skill" "$last/broken-link"
reject "$source" "$scratch/symlink-target"
[ ! -e "$scratch/symlink-target" ] || fail 'source symlink created target'
rm "$last/broken-link"
mkfifo "$last/pipe"
reject "$source" "$scratch/special-target"
[ ! -e "$scratch/special-target" ] || fail 'special file created target'
rm "$last/pipe"
mkdir "$scratch/link-collision"
ln -s "$source/experimental-development" "$scratch/link-collision/experimental-development"
reject "$source" "$scratch/link-collision"
[ ! -e "$scratch/link-collision/run-as-orchestrator" ] || fail 'destination link caused partial install'
reject "$source" "$last/nested-target"
[ ! -e "$last/nested-target" ] || fail 'installed inside source bundle'
reject "$source" "$scratch/no-parent/skills"
[ ! -e "$scratch/no-parent" ] || fail 'created missing parent'
reject
reject "$source" ''
printf 'PASS: symlinks, special files, overlap, missing parent, explicit arguments\n'
