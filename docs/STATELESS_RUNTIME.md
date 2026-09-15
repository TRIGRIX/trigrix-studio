# Stateless runtime

Persistent shape values are encoded in compact JSON, compressed zlib, encoded Base64URL and signed truncated HMAC-SHA256. The key is derived from `BOT_TOKEN`. Capsule is shown as Telegram spoiler in an interactive post.

Inline callback contains only a short runtime ID block and port. When responding to ForceReply, context is extracted from `reply_to_message`. Dictionary records are stored as a pair of `dictionary + id`, and the full record is restored from compiled project data. The default limit is 1,400 characters.

