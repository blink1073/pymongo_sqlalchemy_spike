#!/usr/bin/env bash
# Builds py_mongosqltranslate from the vendored sdist and installs it into the
# spike venv.
#
# Prerequisites (one-off):
#   1. rustup:  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
#                 | sh -s -- -y --profile minimal --default-toolchain stable
#   2. sdists:  mkdir -p vendor && unzip -j -o mongosql-pythonbindings.zip \
#                 'mongosql-pythonbindings/wheels/py_mongosqltranslate-0.1.0.tar.gz' -d vendor/ \
#               && tar xzf vendor/py_mongosqltranslate-0.1.0.tar.gz -C vendor/
#
# Why the debug profile: the release build (LTO + codegen-units=1) is OOM-killed
# on this 3 GB sandbox while compiling the mongosql crate. The dev profile
# compiles in about a minute and is plenty for tests.
set -euo pipefail
cd "$(dirname "$0")/../.."  # repo root

export PATH="$HOME/.cargo/bin:$PATH"
export CARGO_BUILD_JOBS=1
export CARGO_PROFILE_DEV_DEBUG=0
export VIRTUAL_ENV="$PWD/mongosql-dbapi-spike/.venv"

mongosql-dbapi-spike/.venv/bin/maturin develop \
  -m vendor/py_mongosqltranslate-0.1.0/py-mongosqltranslate/Cargo.toml
