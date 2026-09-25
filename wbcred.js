#!/usr/bin/env node
/**
 * wbcred.js — WorkBuddy 凭据解密 helper（零依赖）
 *
 * 背景：WorkBuddy 桌面端 5.3.x 起，workbuddy-desktop.info 中的敏感字段改为
 * 静态加密存储：{"$wbEncrypted":1,"envelope":"<base64(JSON envelope)>"}。
 * envelope 为 suite 1 字段级信封 {suite,keyId,nonce,authTag,ciphertext}，
 * AES-256-GCM，密钥 = sha256(atRestSecretKey)，AAD 域含 "WBEV1"/"sym-v1"/keyId。
 * atRestSecretKey 由魔改 Electron Framework 以 native binding
 * `electron_browser_workbuddy_storage.loggerGet()` 提供——因此本脚本必须用
 * WorkBuddy 自带的 Electron 二进制以 ELECTRON_RUN_AS_NODE=1 运行，系统 node 无效。
 *
 * 用法：
 *   ELECTRON_RUN_AS_NODE=1 <WorkBuddy>/Contents/MacOS/Electron wbcred.js <auth.json 路径>
 * 输出（stdout，单行 JSON）：
 *   {"result":"OK","session":{...解密后的完整对象...}}
 *   {"result":"NO_BINDING"|"NO_KEY"|"READ_FAIL"|"DECRYPT_FAIL","detail":"..."}
 * 安全约定：不打印任何令牌明文以外的调试信息；密钥只在内存中，不落盘。
 */
"use strict";

const fs = require("fs");
const crypto = require("crypto");

function fail(result, detail) {
  process.stdout.write(JSON.stringify({ result, detail: detail || "" }));
  process.exit(1);
}

// --- at-rest-crypto 的 AAD 构造（与桌面端 suite 1 sym-v1 字段级信封一致） ---
function encodeUint32(value) {
  const b = Buffer.alloc(4);
  b.writeUInt32BE(value);
  return b;
}
function encodeLengthPrefixed(value) {
  const bytes = Buffer.from(value, "utf8");
  return Buffer.concat([encodeUint32(bytes.length), bytes]);
}
function buildFieldAad(keyId, suite) {
  return Buffer.concat([
    Buffer.from("WB-AAD\0", "ascii"),
    Buffer.from([1]), // 域版本
    encodeLengthPrefixed("WBEV1"), // field 格式 ID
    encodeLengthPrefixed("sym-v1"),
    encodeUint32(suite),
    encodeLengthPrefixed(keyId),
    Buffer.from([2]), // FRAMING_CODE.field
    Buffer.from([0]), // 无 sequence
    Buffer.from([0]), // final 未定义
  ]);
}

function decryptField(key, envelopeB64) {
  const env = JSON.parse(Buffer.from(envelopeB64, "base64").toString("utf8"));
  const decipher = crypto.createDecipheriv(
    "aes-256-gcm",
    key,
    Buffer.from(env.nonce, "base64"),
    { authTagLength: 16 }
  );
  decipher.setAAD(buildFieldAad(env.keyId, env.suite));
  decipher.setAuthTag(Buffer.from(env.authTag, "base64"));
  return Buffer.concat([
    decipher.update(Buffer.from(env.ciphertext, "base64")),
    decipher.final(),
  ]).toString("utf8");
}

function isEncrypted(value) {
  return (
    typeof value === "object" && value !== null && !Array.isArray(value) &&
    value.$wbEncrypted === 1 && typeof value.envelope === "string"
  );
}

function decryptTree(key, node, stats) {
  if (Array.isArray(node)) return node.map((v) => decryptTree(key, v, stats));
  if (!isEncrypted(node)) {
    if (node && typeof node === "object") {
      const out = {};
      for (const [k, v] of Object.entries(node)) out[k] = decryptTree(key, v, stats);
      return out;
    }
    return node;
  }
  try {
    const plain = decryptField(key, node.envelope);
    stats.decrypted += 1;
    // 字段明文多为 JSON 编码值（如 "uid 字符串"），但也有裸字符串（如 JWT 令牌）——
    // 统一尝试 JSON.parse，失败则按原始字符串返回。
    try {
      return JSON.parse(plain);
    } catch {
      return plain;
    }
  } catch (e) {
    stats.failed += 1;
    return { $wbDecryptionFailed: String((e && e.message) || e) };
  }
}

function main() {
  const authFile = process.argv[2];
  if (!authFile) fail("READ_FAIL", "missing auth file argument");

  let binding;
  try {
    binding = process._linkedBinding("electron_browser_workbuddy_storage");
  } catch {
    fail("NO_BINDING", "electron_browser_workbuddy_storage unavailable; use WorkBuddy's Electron binary with ELECTRON_RUN_AS_NODE=1");
  }
  if (!binding || typeof binding.loggerGet !== "function") {
    fail("NO_BINDING", "loggerGet missing");
  }

  let raw;
  try {
    raw = binding.loggerGet();
  } catch (e) {
    fail("NO_KEY", String((e && e.message) || e));
  }
  const payload = JSON.parse(typeof raw === "string" ? raw : JSON.stringify(raw));
  if (!payload.atRestSecretKey) fail("NO_KEY", "no atRestSecretKey in payload");

  const key = crypto.createHash("sha256").update(payload.atRestSecretKey, "utf8").digest();

  let doc;
  try {
    doc = JSON.parse(fs.readFileSync(authFile, "utf8"));
  } catch (e) {
    fail("READ_FAIL", String((e && e.message) || e));
  }

  const stats = { decrypted: 0, failed: 0 };
  const session = decryptTree(key, doc, stats);
  process.stdout.write(JSON.stringify({ result: "OK", stats, session }));
}

main();
