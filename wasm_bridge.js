#!/usr/bin/env node
/**
 * WASM Decryption Bridge — QMC & KGM format decryption.
 *
 * This is a thin bridge between Python and the WASM-based decryption modules.
 * It loads the @xhacker/qmcwasm and @xhacker/kgmwasm npm packages (which must
 * be installed in the same directory) and exposes a simple file-in/file-out CLI.
 *
 * Usage:
 *   node wasm_bridge.js <format> <input_file> <output_file>
 *
 * Where <format> is one of: qmc, kgm
 */

const fs = require('fs');
const path = require('path');

// Load WASM modules from local node_modules
let QmcCryptoModule, KgmCryptoModule;

async function loadModules() {
  if (!QmcCryptoModule) {
    QmcCryptoModule = require('@xhacker/qmcwasm/QmcWasmBundle');
  }
  if (!KgmCryptoModule) {
    KgmCryptoModule = require('@xhacker/kgmwasm/KgmWasmBundle');
  }
}

const CHUNK_SIZE = 2 * 1024 * 1024; // 2MB processing chunks

/**
 * Decrypt a QMC-encrypted file.
 *
 * QMC files have encrypted audio data followed by a footer containing
 * metadata. The WASM module's preDec() reads the tail to determine
 * encryption parameters, then decBlob() decrypts chunks position-dependently.
 */
async function decryptQmc(inputPath, outputPath) {
  await loadModules();
  const QmcCrypto = await QmcCryptoModule();

  const fileData = fs.readFileSync(inputPath);
  const ext = path.extname(inputPath).slice(1).toLowerCase();

  // Allocate WASM memory buffer
  const bufPtr = QmcCrypto._malloc(CHUNK_SIZE);

  // Pass file tail to preDec for initialization
  const tailChunkSize = Math.min(CHUNK_SIZE, fileData.length);
  const tailStart = fileData.length - tailChunkSize;
  QmcCrypto.writeArrayToMemory(
    new Uint8Array(fileData.buffer.slice(tailStart)),
    bufPtr
  );

  const tailSize = QmcCrypto.preDec(bufPtr, tailChunkSize, '.' + ext);
  if (tailSize === -1) {
    QmcCrypto._free(bufPtr);
    throw new Error(QmcCrypto.getErr() || 'QMC preDec failed');
  }

  const songId = QmcCrypto.getSongId();

  // Decrypt audio data in chunks (everything except the footer tail)
  const audioLen = fileData.length - tailSize;
  const outputParts = [];
  let offset = 0;
  let remaining = audioLen;

  while (remaining > 0) {
    const blockSize = Math.min(remaining, CHUNK_SIZE);
    const blockData = new Uint8Array(
      fileData.buffer.slice(offset, offset + blockSize)
    );
    QmcCrypto.writeArrayToMemory(blockData, bufPtr);
    const decryptedLen = QmcCrypto.decBlob(bufPtr, blockSize, offset);
    outputParts.push(
      Buffer.from(QmcCrypto.HEAPU8.slice(bufPtr, bufPtr + decryptedLen))
    );
    offset += blockSize;
    remaining -= blockSize;
  }

  QmcCrypto._free(bufPtr);

  // Write output
  const output = Buffer.concat(outputParts);
  fs.writeFileSync(outputPath, output);
  fs.writeFileSync(outputPath + '.meta', JSON.stringify({ songId }));

  return { size: output.length, songId };
}

/**
 * Decrypt a KGM-encrypted file (Kugou Music).
 *
 * KGM files have a header followed by encrypted audio.
 * preDec() determines the header size, then decBlob() decrypts the rest.
 */
async function decryptKgm(inputPath, outputPath) {
  await loadModules();
  const KgmCrypto = await KgmCryptoModule();

  const fileData = fs.readFileSync(inputPath);

  // Allocate WASM memory buffer
  const bufPtr = KgmCrypto._malloc(CHUNK_SIZE);

  // Pass file head to preDec for initialization
  const headChunkSize = Math.min(CHUNK_SIZE, fileData.length);
  KgmCrypto.writeArrayToMemory(
    new Uint8Array(fileData.buffer.slice(0, headChunkSize)),
    bufPtr
  );

  const ext = path.extname(inputPath).slice(1).toLowerCase();
  const headerSize = KgmCrypto.preDec(bufPtr, headChunkSize, ext);
  if (headerSize < 0) {
    KgmCrypto._free(bufPtr);
    throw new Error('KGM preDec failed');
  }

  // Decrypt audio data (everything after header) in chunks
  const audioOffset = headerSize;
  const audioLen = fileData.length - headerSize;
  const outputParts = [];
  let offset = audioOffset;
  let remaining = audioLen;

  while (remaining > 0) {
    const blockSize = Math.min(remaining, CHUNK_SIZE);
    const blockData = new Uint8Array(
      fileData.buffer.slice(offset, offset + blockSize)
    );
    KgmCrypto.writeArrayToMemory(blockData, bufPtr);
    KgmCrypto.decBlob(bufPtr, blockSize, offset - audioOffset);
    outputParts.push(
      Buffer.from(KgmCrypto.HEAPU8.slice(bufPtr, bufPtr + blockSize))
    );
    offset += blockSize;
    remaining -= blockSize;
  }

  KgmCrypto._free(bufPtr);

  const output = Buffer.concat(outputParts);
  fs.writeFileSync(outputPath, output);

  return { size: output.length };
}

// ============================================================
// CLI
// ============================================================
async function main() {
  const args = process.argv.slice(2);
  if (args.length < 3) {
    console.error('Usage: node wasm_bridge.js <qmc|kgm> <input> <output>');
    process.exit(1);
  }

  const [format, inputPath, outputPath] = args;

  try {
    let result;
    if (format === 'qmc') {
      result = await decryptQmc(inputPath, outputPath);
    } else if (format === 'kgm') {
      result = await decryptKgm(inputPath, outputPath);
    } else {
      console.error('Unknown format:', format);
      process.exit(1);
    }
    console.log(JSON.stringify(result));
  } catch (err) {
    console.error('DECRYPT_ERROR:', err.message);
    process.exit(1);
  }
}

main();
