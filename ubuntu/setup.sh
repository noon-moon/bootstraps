#!/usr/bin/env zsh
set -euo pipefail

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

info()    { print -P "%F{yellow}==> $1%f"; }
success() { print -P "%F{green}✓ $1%f"; }

# ── APT ──────────────────────────────────────────────────────────────────────
info "Updating APT"
sudo apt-get update -y

# ── gh CLI apt repo ──────────────────────────────────────────────────────────
if ! command -v gh &>/dev/null; then
  info "Adding GitHub CLI apt repo"
  sudo mkdir -p -m 755 /etc/apt/keyrings
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
  sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
  sudo apt-get update -y
fi

# ── CLI packages ─────────────────────────────────────────────────────────────
PACKAGES=(
  autojump   # directory jumping (j <dir>)
  fzf        # fuzzy finder
  neovim
  python3
  python3-pip
  git
  gh         # GitHub CLI
  jq
  tree
  wget
  ripgrep
  zsh
)

info "Installing APT packages"
sudo apt-get install -y "${PACKAGES[@]}"

# ── ZSH / Oh My Zsh ──────────────────────────────────────────────────────────
if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
  info "Installing Oh My Zsh"
  RUNZSH=no CHSH=no sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi

# ── nvm + Node ───────────────────────────────────────────────────────────────
if [[ ! -d "$HOME/.nvm" ]]; then
  info "Installing nvm"
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
fi

export NVM_DIR="$HOME/.nvm"
[[ -s "$NVM_DIR/nvm.sh" ]] && source "$NVM_DIR/nvm.sh"

info "Installing Node LTS"
nvm install --lts
nvm use --lts
nvm alias default node

info "Installing global npm packages"
npm install -g typescript ts-node

# ── Rust ─────────────────────────────────────────────────────────────────────
if ! command -v rustup &>/dev/null; then
  info "Installing Rust via rustup"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path
fi
source "$HOME/.cargo/env"
rustup update stable

# ── .zshrc ───────────────────────────────────────────────────────────────────
ZSHRC="$HOME/.zshrc"

write_block() {
  local marker="$1" content="$2"
  if ! grep -qF "$marker" "$ZSHRC" 2>/dev/null; then
    printf '\n# %s\n%s\n' "$marker" "$content" >> "$ZSHRC"
  fi
}

info "Configuring .zshrc"

# Ensure ZSH path and OMZ are set
if ! grep -q 'ZSH=' "$ZSHRC" 2>/dev/null; then
  cat >> "$ZSHRC" <<'EOF'

export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="mira"
plugins=(git autojump fzf aliases)
source $ZSH/oh-my-zsh.sh
alias vi=nvim
EOF
fi

write_block "autojump" '[ -f /usr/share/autojump/autojump.sh ] && . /usr/share/autojump/autojump.sh'
write_block "fzf" 'source <(fzf --zsh)'
write_block "nvm" 'export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"'
write_block "cargo" 'source "$HOME/.cargo/env"'

success "Done! Open a new shell or run: source ~/.zshrc"

cat <<'EOF'

Manual steps:
  - chsh -s $(which zsh)   (if zsh isn't already the login shell)
  - gh auth login
  - Continue with the VPS provisioning sequence: UFW, Tailscale, Docker, repo clones
EOF
