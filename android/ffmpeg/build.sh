#!/usr/bin/env bash
# Builds the small ffmpeg the Android app ships for the cutscene movies (tools/usm.py: H.264 copied into mp4,
# CRI ADX / HCA audio -> AAC; tools/build_web.py: a JPEG poster frame). LGPL build: no GPL parts (no libx264).
# Output: out/<abi>/libffmpeg.so (an executable; Android only unpacks lib*.so files, so it carries that name)
# and license/COPYING.LGPLv2.1. Needs the Android NDK (ANDROID_NDK_HOME, or $ANDROID_HOME/ndk/<version>).
#
#   android/ffmpeg/build.sh [arm64-v8a] [x86_64]
set -euo pipefail
VER=7.1.5
SHA256=de668509caf9e35e3cd162473441fdb29538c6d96ed080292b3cf9e6fc5d558f
API=24
HERE=$(cd "$(dirname "$0")" && pwd)
NDK=${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}
[ -n "$NDK" ] || NDK=$(ls -d "${ANDROID_HOME:?set ANDROID_NDK_HOME or ANDROID_HOME}"/ndk/* | sort -V | tail -1)
TC=$NDK/toolchains/llvm/prebuilt/linux-x86_64
SRC=$HERE/src/ffmpeg-$VER

if [ ! -d "$SRC" ]; then
  mkdir -p "$HERE/src"
  curl -sSL -o "$HERE/src/ffmpeg-$VER.tar.xz" "https://ffmpeg.org/releases/ffmpeg-$VER.tar.xz"
  echo "$SHA256  $HERE/src/ffmpeg-$VER.tar.xz" | sha256sum -c -
  tar -C "$HERE/src" -xf "$HERE/src/ffmpeg-$VER.tar.xz"
fi

for ABI in ${@:-arm64-v8a x86_64}; do
  case $ABI in
    arm64-v8a) ARCH=aarch64; TRIPLE=aarch64-linux-android; EXTRA=() ;;
    x86_64)    ARCH=x86_64;  TRIPLE=x86_64-linux-android;  EXTRA=(--disable-x86asm) ;;  # the emulator
    *) echo "unknown ABI $ABI" >&2; exit 1 ;;
  esac
  OUT=$HERE/out/$ABI
  if [ -f "$OUT/libffmpeg.so" ]; then echo "$ABI: already built"; continue; fi
  B=$HERE/build/$ABI
  rm -rf "$B"; mkdir -p "$B"; cd "$B"
  "$SRC/configure" --target-os=android --arch=$ARCH --enable-cross-compile \
    --cc="$TC/bin/${TRIPLE}${API}-clang" --cxx="$TC/bin/${TRIPLE}${API}-clang++" \
    --nm="$TC/bin/llvm-nm" --ar="$TC/bin/llvm-ar" --ranlib="$TC/bin/llvm-ranlib" --strip="$TC/bin/llvm-strip" \
    --enable-pic --disable-shared --enable-static --disable-doc --disable-debug --disable-network \
    --disable-autodetect --disable-everything --disable-programs --enable-ffmpeg --disable-avdevice \
    --enable-protocol=file,pipe \
    --enable-demuxer=h264,adx,hca,mov \
    --enable-muxer=mp4,mov,image2 \
    --enable-parser=h264,adx \
    --enable-decoder=h264,adpcm_adx,hca \
    --enable-encoder=aac,mjpeg \
    --enable-filter=aresample,aformat,anull,null,format,scale \
    "${EXTRA[@]}" > configure.log
  make -j"$(nproc)" ffmpeg > make.log
  mkdir -p "$OUT"
  "$TC/bin/llvm-strip" -o "$OUT/libffmpeg.so" ffmpeg
  echo "$ABI: $(du -h "$OUT/libffmpeg.so" | cut -f1)"
done
mkdir -p "$HERE/license"
cp "$SRC/COPYING.LGPLv2.1" "$HERE/license/"
echo "FFmpeg $VER (https://ffmpeg.org/releases/ffmpeg-$VER.tar.xz), LGPL 2.1 build; configuration: android/ffmpeg/build.sh" > "$HERE/license/README.txt"
