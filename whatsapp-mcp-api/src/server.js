import http from "node:http";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import QRCode from "qrcode";
import qrcode from "qrcode-terminal";
import pkg from "whatsapp-web.js";

const { Client, LocalAuth } = pkg;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");

const host = process.env.WHATSAPP_MCP_HOST || "127.0.0.1";
const port = Number(process.env.WHATSAPP_MCP_PORT || 8790);
const authDir = path.resolve(process.env.WHATSAPP_AUTH_DIR || path.join(rootDir, ".wwebjs_auth"));
const chromeExecutablePath =
  process.env.WHATSAPP_CHROME_EXECUTABLE ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const headless = String(process.env.WHATSAPP_HEADLESS || "false").toLowerCase() === "true";

const jsonHeaders = {
  "content-type": "application/json; charset=utf-8",
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,OPTIONS",
  "access-control-allow-headers": "content-type,mcp-session-id",
  "access-control-expose-headers": "mcp-session-id"
};

function normalizePhone(phoneNumber) {
  const digits = String(phoneNumber || "").replace(/\D/g, "");
  if (digits.length < 8 || digits.length > 15) {
    throw new Error("phone_number must include country code and contain 8-15 digits");
  }
  return digits;
}

function chatId(phoneNumber) {
  return `${normalizePhone(phoneNumber)}@c.us`;
}

function toolText(payload) {
  return {
    content: [
      {
        type: "text",
        text: typeof payload === "string" ? payload : JSON.stringify(payload, null, 2)
      }
    ]
  };
}

class WhatsAppWebClient {
  constructor() {
    this.client = null;
    this.starting = null;
    this.ready = false;
    this.state = "stopped";
    this.lastQr = null;
    this.lastError = null;
    this.info = null;
  }

  status() {
    return {
      state: this.state,
      ready: this.ready,
      authenticated: this.ready,
      auth_dir: authDir,
      chrome_executable: chromeExecutablePath,
      headless,
      has_qr: Boolean(this.lastQr),
      last_error: this.lastError,
      account: this.info
        ? {
            wid: this.info.wid?._serialized || null,
            pushname: this.info.pushname || null,
            platform: this.info.platform || null
          }
        : null
    };
  }

  async start() {
    if (this.ready) {
      return this.status();
    }

    if (this.client) {
      return this.status();
    }

    if (this.starting) {
      await this.starting;
      return this.status();
    }

    this.starting = this.#initialize();
    try {
      await this.starting;
      return this.status();
    } finally {
      this.starting = null;
    }
  }

  async #initialize() {
    this.state = "starting";
    this.lastError = null;

    const client = new Client({
      authStrategy: new LocalAuth({
        dataPath: authDir,
        clientId: "default"
      }),
      puppeteer: {
        executablePath: chromeExecutablePath,
        headless,
        args: [
          "--disable-dev-shm-usage",
          "--disable-gpu",
          "--no-first-run",
          "--no-default-browser-check"
        ]
      }
    });

    this.client = client;

    client.on("qr", (qr) => {
      this.lastQr = qr;
      this.state = "qr";
      console.log("WhatsApp Web auth QR received. Scan it in the opened Chrome window.");
      qrcode.generate(qr, { small: true });
    });

    client.on("authenticated", () => {
      this.state = "authenticated";
      this.lastError = null;
      console.log("WhatsApp Web authenticated.");
    });

    client.on("ready", () => {
      this.ready = true;
      this.state = "ready";
      this.lastQr = null;
      this.info = client.info || null;
      console.log("WhatsApp Web client ready.");
    });

    client.on("auth_failure", (message) => {
      this.ready = false;
      this.state = "auth_failure";
      this.lastError = message || "WhatsApp Web auth failed";
      console.error(`WhatsApp auth failure: ${this.lastError}`);
    });

    client.on("disconnected", (reason) => {
      this.ready = false;
      this.state = "disconnected";
      this.lastError = reason || null;
      this.info = null;
      console.warn(`WhatsApp Web disconnected: ${reason}`);
    });

    await client.initialize();
  }

  async ensureReady(timeoutMs = 120000) {
    await this.start();

    if (this.ready) {
      return;
    }

    const deadline = Date.now() + timeoutMs;
    while (!this.ready && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      if (this.state === "auth_failure") {
        throw new Error(this.lastError || "WhatsApp auth failed");
      }
    }

    if (!this.ready) {
      throw new Error("WhatsApp Web is not ready yet. Scan the QR code in Chrome, then retry.");
    }
  }

  async sendMessage(phoneNumber, message) {
    if (!message || typeof message !== "string") {
      throw new Error("message must be a non-empty string");
    }

    await this.ensureReady();
    const to = chatId(phoneNumber);
    const sent = await this.client.sendMessage(to, message);

    return {
      ok: true,
      to: normalizePhone(phoneNumber),
      chat_id: to,
      message_id: sent.id?._serialized || sent.id?.id || null,
      timestamp: new Date().toISOString()
    };
  }

  async pairingCode(phoneNumber) {
    if (!this.client) {
      await this.start();
    }

    if (!this.client) {
      throw new Error("WhatsApp client is not available");
    }

    if (this.ready) {
      return {
        already_authenticated: true,
        code: null,
        status: this.status()
      };
    }

    const phone = normalizePhone(phoneNumber);
    const code = await this.client.requestPairingCode(phone, true, 180000);
    return {
      already_authenticated: false,
      phone_number: phone,
      code,
      instructions: "WhatsApp -> Linked devices -> Link a device -> Link with phone number instead"
    };
  }

  async logout() {
    if (this.client) {
      await this.client.logout();
      await this.client.destroy();
    }

    this.client = null;
    this.ready = false;
    this.state = "stopped";
    this.lastQr = null;
    this.info = null;
    return { ok: true };
  }
}

const whatsapp = new WhatsAppWebClient();

const tools = [
  {
    name: "whatsapp_status",
    description: "Check WhatsApp Web auth and local Chrome session status.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false }
  },
  {
    name: "whatsapp_start_auth",
    description: "Open Chrome and start WhatsApp Web authentication if needed.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false }
  },
  {
    name: "whatsapp_pairing_code",
    description: "Generate a WhatsApp Linked Devices phone-number pairing code for this API session.",
    inputSchema: {
      type: "object",
      required: ["phone_number"],
      properties: {
        phone_number: {
          type: "string",
          description: "Phone number with country code, digits or E.164 format."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "whatsapp_send_message",
    description: "Send a WhatsApp text message through the authenticated WhatsApp Web session.",
    inputSchema: {
      type: "object",
      required: ["phone_number", "message"],
      properties: {
        phone_number: {
          type: "string",
          description: "Phone number with country code, digits or E.164 format."
        },
        message: {
          type: "string",
          description: "Text message to send."
        }
      },
      additionalProperties: false
    }
  },
  {
    name: "whatsapp_logout",
    description: "Logout WhatsApp Web for this local session.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false }
  }
];

async function callTool(name, args = {}) {
  if (name === "whatsapp_status") {
    return toolText(whatsapp.status());
  }

  if (name === "whatsapp_start_auth") {
    return toolText(await whatsapp.start());
  }

  if (name === "whatsapp_pairing_code") {
    return toolText(await whatsapp.pairingCode(args.phone_number));
  }

  if (name === "whatsapp_send_message") {
    return toolText(await whatsapp.sendMessage(args.phone_number, args.message));
  }

  if (name === "whatsapp_logout") {
    return toolText(await whatsapp.logout());
  }

  throw new Error(`Unknown tool: ${name}`);
}

async function readJson(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(chunk);
  }

  if (!chunks.length) {
    return {};
  }

  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function sendJson(res, status, body, extraHeaders = {}) {
  const payload = Buffer.from(JSON.stringify(body, null, 2));
  res.writeHead(status, {
    ...jsonHeaders,
    ...extraHeaders,
    "content-length": payload.length
  });
  res.end(payload);
}

function sendHtml(res, status, html) {
  const payload = Buffer.from(html);
  res.writeHead(status, {
    "content-type": "text/html; charset=utf-8",
    "content-length": payload.length
  });
  res.end(payload);
}

function sendError(res, status, message, id = null) {
  sendJson(res, status, {
    jsonrpc: "2.0",
    id,
    error: {
      code: status === 400 ? -32602 : -32000,
      message
    }
  });
}

async function handleMcp(req, res) {
  const message = await readJson(req);
  const { id, method, params = {} } = message;
  const sessionId = req.headers["mcp-session-id"] || randomUUID();
  const headers = { "mcp-session-id": sessionId };

  if (method === "initialize") {
    sendJson(
      res,
      200,
      {
        jsonrpc: "2.0",
        id,
        result: {
          protocolVersion: params.protocolVersion || "2024-11-05",
          capabilities: { tools: {} },
          serverInfo: { name: "whatsapp-mcp-api", version: "0.2.0" }
        }
      },
      headers
    );
    return;
  }

  if (method === "notifications/initialized") {
    res.writeHead(202, { ...jsonHeaders, ...headers });
    res.end();
    return;
  }

  if (method === "tools/list") {
    sendJson(res, 200, { jsonrpc: "2.0", id, result: { tools } }, headers);
    return;
  }

  if (method === "tools/call") {
    const result = await callTool(params.name, params.arguments || {});
    sendJson(res, 200, { jsonrpc: "2.0", id, result }, headers);
    return;
  }

  sendJson(
    res,
    200,
    {
      jsonrpc: "2.0",
      id,
      error: { code: -32601, message: `Method not found: ${method}` }
    },
    headers
  );
}

async function handleRest(req, res, url) {
  if (req.method === "GET" && url.pathname === "/qr") {
    const status = whatsapp.status();
    let qrHtml = "<p>No QR is available yet. Start auth, then refresh this page.</p>";

    if (whatsapp.lastQr) {
      const dataUrl = await QRCode.toDataURL(whatsapp.lastQr, { margin: 2, width: 360 });
      qrHtml = `<img src="${dataUrl}" alt="WhatsApp Web QR code" width="360" height="360" />`;
    }

    sendHtml(
      res,
      200,
      `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="refresh" content="5" />
  <title>WhatsApp MCP QR</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 32px; background: #f6f7f8; color: #111; }
    main { max-width: 520px; margin: 0 auto; padding: 24px; background: white; border: 1px solid #ddd; border-radius: 8px; }
    img { display: block; margin: 16px auto; image-rendering: pixelated; }
    code { background: #f1f1f1; padding: 2px 6px; border-radius: 4px; }
  </style>
</head>
<body>
  <main>
    <h1>WhatsApp Web Auth</h1>
    ${qrHtml}
    <p>Status: <code>${status.state}</code></p>
    <p>Scan with WhatsApp: Settings -> Linked devices -> Link a device.</p>
  </main>
</body>
</html>`
    );
    return;
  }

  if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/health")) {
    sendJson(res, 200, {
      ok: true,
      name: "whatsapp-mcp-api",
      mcp: `http://${host}:${port}/mcp`,
      status: whatsapp.status()
    });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/status") {
    sendJson(res, 200, whatsapp.status());
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/auth/start") {
    sendJson(res, 200, await whatsapp.start());
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/pairing-code") {
    const body = await readJson(req);
    sendJson(res, 200, await whatsapp.pairingCode(body.phone_number));
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/send") {
    const body = await readJson(req);
    sendJson(res, 200, await whatsapp.sendMessage(body.phone_number, body.message));
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/logout") {
    sendJson(res, 200, await whatsapp.logout());
    return;
  }

  sendJson(res, 404, { error: "not found" });
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "OPTIONS") {
      res.writeHead(204, jsonHeaders);
      res.end();
      return;
    }

    const url = new URL(req.url || "/", `http://${req.headers.host || `${host}:${port}`}`);

    if (req.method === "POST" && url.pathname === "/mcp") {
      await handleMcp(req, res);
      return;
    }

    await handleRest(req, res, url);
  } catch (error) {
    const status = error instanceof SyntaxError ? 400 : 500;
    sendError(res, status, error.message, null);
  }
});

server.listen(port, host, () => {
  console.log(`WhatsApp MCP API listening on http://${host}:${port}`);
  console.log(`MCP endpoint: http://${host}:${port}/mcp`);
  console.log(`Chrome executable: ${chromeExecutablePath}`);
  console.log(`WhatsApp Web auth directory: ${authDir}`);
});
