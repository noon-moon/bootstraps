# Skills mount placeholder

OpenCode role skills are mounted into the container at
/home/agent/.config/opencode/skills (see compose OPENCODE_SKILLS_DIR).
This directory ships empty: the deployment never silently claims host
skills are loaded in the container — the mount is the explicit seam.
