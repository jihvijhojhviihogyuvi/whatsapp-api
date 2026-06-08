# WhatsApp API MCP

Local WhatsApp REST and MCP server backed by `whatsapp-web.js`.

The server links to a personal WhatsApp account through WhatsApp Linked Devices, saves the session locally, and then exposes message sending through API calls. After the one-time pairing step, you can send messages without manually opening WhatsApp Web.

## Project

The app lives in:

```text
whatsapp-mcp-api/
```
## Clone

```powershell
git clone https://github.com/jihvijhojhviihogyuvi/whatsapp-api.git
```
## Install

```powershell
cd whatsapp-api/whatsapp-mcp-api
npm install
```

## Run

```powershell
npm start
```

Default local server:

```text
http://127.0.0.1:8790
```

## Pair WhatsApp

Request a numeric pairing code:

```powershell
curl.exe -X POST http://127.0.0.1:8790/api/pairing-code `
  -H "content-type: application/json" `
  -d "{\"phone_number\":\"15551234567\"}"
```

On your phone:

```text
WhatsApp -> Linked devices -> Link a device -> Link with phone number instead
```

Enter the returned code. The linked session is saved locally in:

```text
whatsapp-mcp-api/.wwebjs_auth/session-default
```

Do not delete `.wwebjs_auth` if you want to keep the login. It is intentionally ignored by git because it contains sensitive session data.

## Send a Message

```powershell
curl.exe -X POST http://127.0.0.1:8790/api/send `
  -H "content-type: application/json" `
  -d "{\"phone_number\":\"15551234567\",\"message\":\"hello from api\"}"
```

## List Chats

```powershell
curl.exe "http://127.0.0.1:8790/api/chats?limit=20"
```

## Read Last Messages

```powershell
curl.exe "http://127.0.0.1:8790/api/messages?phone_number=15551234567&limit=10"
```

Or with JSON:

```powershell
curl.exe -X POST http://127.0.0.1:8790/api/messages `
  -H "content-type: application/json" `
  -d "{\"phone_number\":\"15551234567\",\"limit\":10}"
```

## MCP Endpoint

```text
POST http://127.0.0.1:8790/mcp
```

Available tools:

- `whatsapp_status`
- `whatsapp_start_auth`
- `whatsapp_pairing_code`
- `whatsapp_send_message`
- `whatsapp_list_chats`
- `whatsapp_read_messages`
- `whatsapp_logout`

## Notes

This project uses an unofficial WhatsApp Web client. Use it only with accounts and recipients you control or have permission to message.
ion to message.
