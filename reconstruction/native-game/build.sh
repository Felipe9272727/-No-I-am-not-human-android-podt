#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$project_dir"
if [[ -x "$project_dir/tools/cargo/bin/cargo" && -z "${CARGO:-}" ]]; then
 export CARGO="$project_dir/tools/cargo/bin/cargo"
 export CARGO_HOME="$project_dir/tools/cargo"
 export RUSTUP_HOME="$project_dir/tools/rustup"
fi
native_dir="$project_dir/reconstruction/native-game"
python3 tools/native-game/generate_production_data.py
python3 tools/reverse-phone/generate_phone_provider.py
python3 tools/reverse-localization/generate_line_metadata_provider.py
python3 tools/reverse-scenes/generate_presentation_provider.py
python3 tools/native-game/build_host.py
cargo_bin="${CARGO:-/root/.cargo/bin/cargo}"
"$cargo_bin" test --locked --manifest-path reconstruction/yarn-runtime/Cargo.toml
"$cargo_bin" test --locked --manifest-path "$native_dir/bridge/Cargo.toml"
"$cargo_bin" build --locked --release --manifest-path "$native_dir/bridge/Cargo.toml"
"${CXX:-g++}" -std=c++17 -Wall -Wextra -Werror -pedantic \
 -I "$native_dir/include" -I "$native_dir/generated" \
 "$native_dir"/src/*.cpp "$native_dir/tests/yarn_integration.cpp" \
 "$native_dir/bridge/target/release/libninah_yarn_bridge.a" \
 -ldl -lpthread -lm -o "$native_dir/build/yarn-integration"
python3 tools/native-game/check_yarn_integration.py
