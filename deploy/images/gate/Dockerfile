FROM caddy@sha256:af32e97399febea808609119bb21544d0265c58a02836576e32a2d082c262c17

# Copying creates a fresh inode without the upstream file capability. The
# gate uses high ports and must execute with an empty capability bounding set.
RUN cp /usr/bin/caddy /usr/bin/caddy.unprivileged \
    && mv /usr/bin/caddy.unprivileged /usr/bin/caddy

USER 10001:10001
