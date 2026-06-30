#!/usr/bin/env zsh
set -euo pipefail

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

info()    { print -P "%F{yellow}==> $1%f"; }
success() { print -P "%F{green}✓ $1%f"; }

# ── Homebrew ─────────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
  info "Installing Homebrew"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)"
else
  info "Updating Homebrew"
  brew update
fi

# ── CLI tools ─────────────────────────────────────────────────────────────────
FORMULAE=(
  autojump   # directory jumping (j <dir>)
  fzf        # fuzzy finder
  neovim
  python@3.14
  git
  gh         # GitHub CLI
  jq
  tree
  wget
  ripgrep
)

info "Installing Homebrew formulae"
for f in $FORMULAE; do
  brew list "$f" &>/dev/null || brew install "$f"
done

# ── GUI apps ──────────────────────────────────────────────────────────────────
CASKS=(
  iterm2
  visual-studio-code
  docker
  1password
  claude-code
  obsidian
  fantastical
  font-monaspace
  firefox
  discord
  dropbox
  magnet
  amphetamine
  zoom
)

info "Installing Homebrew casks"
for c in $CASKS; do
  brew list --cask "$c" &>/dev/null || brew install --cask "$c"
done

# ── fzf shell integration ─────────────────────────────────────────────────────
$(brew --prefix)/opt/fzf/install --key-bindings --completion --no-update-rc --no-bash --no-fish 2>/dev/null || true

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
plugins=(git autojump fzf aliases 1password)
source $ZSH/oh-my-zsh.sh
alias vi=nvim
EOF
fi

write_block "autojump" '[ -f /opt/homebrew/etc/profile.d/autojump.sh ] && . /opt/homebrew/etc/profile.d/autojump.sh'
write_block "fzf" 'source <(fzf --zsh)'
write_block "nvm" 'export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"'
write_block "cargo" 'source "$HOME/.cargo/env"'
write_block "homebrew" 'eval "$(/opt/homebrew/bin/brew shellenv)"'

success "Done! Open a new terminal tab or run: source ~/.zshrc"

cat <<'EOF'

Manual steps:
  - Sign in to 1Password
  - Sign in to Fantastical / Dropbox / Zoom
  - Install from App Store: Magnet, Amphetamine (if not via cask)
  - Set iTerm2 as default terminal
EOF
