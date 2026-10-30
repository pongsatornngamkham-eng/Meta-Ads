export class ApiError extends Error { constructor(message:string, public status:number){super(message);} }
const LOCAL = typeof window !== 'undefined' && ['localhost','127.0.0.1','::1','[::1]'].includes(window.location.hostname);
const CONNECTION_ERROR = LOCAL
  ? 'ติดต่อระบบ FastAPI ไม่ได้ โปรดเปิด backend ที่พอร์ต 8000 แล้วลองอีกครั้ง'
  : 'ติดต่อระบบ Dashboard ไม่ได้ โปรดลองอีกครั้ง หากยังไม่ได้ให้ผู้ดูแลตรวจเซิร์ฟเวอร์';

// Next.js/proxies can return plain text or HTML when the Python service fails.
// Do not expose their raw bodies or let JSON parsing hide the actionable error.
export async function requestJson<T>(url: string, options: RequestInit = {}, timeoutMs = 20_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  let text: string;
  try {
    response = await fetch(url, { ...options, signal: controller.signal });
    text = await response.text();
  } catch {
    if (controller.signal.aborted) {
      throw new Error(LOCAL ? 'รอนานเกิน 20 วินาที โปรดตรวจว่า backend และ PostgreSQL พร้อมใช้งาน แล้วลองใหม่' : 'ระบบยังตอบกลับไม่สำเร็จภายใน 20 วินาที โปรดลองอีกครั้ง');
    }
    throw new Error(CONNECTION_ERROR);
  } finally {
    clearTimeout(timer);
  }

  let body: unknown;
  try { body = JSON.parse(text); }
  catch { throw new Error(`${CONNECTION_ERROR} (HTTP ${response.status})`); }
  if (!response.ok) {
    const detail = typeof body === 'object' && body !== null && 'detail' in body ? body.detail : null;
    if (typeof detail === 'string' && response.status < 500) throw new ApiError(detail,response.status);
    if (response.status === 503 && typeof detail === 'string' && detail.includes('ฐานข้อมูล')) {
      throw new Error(LOCAL ? 'ฐานข้อมูลยังไม่พร้อม โปรดเปิด Docker Desktop แล้วรัน docker compose up -d db และขั้นตอน init ฐานข้อมูลใน README-WINDOWS.md' : 'ฐานข้อมูลยังไม่พร้อมใช้งาน โปรดลองอีกครั้ง หากยังไม่ได้ให้ผู้ดูแลตรวจระบบ');
    }
    if (response.status >= 500 && typeof detail === 'string') throw new ApiError(detail,response.status);
    if (response.status === 422) throw new Error('ข้อมูลไฟล์ไม่ถูกต้อง โปรดใช้ CSV ตามไฟล์ตัวอย่าง');
    throw new Error(`ระบบประมวลผลไม่สำเร็จ (HTTP ${response.status}) โปรดลองอีกครั้ง`);
  }
  if (typeof body !== 'object' || body === null) throw new Error('ระบบตอบกลับในรูปแบบไม่ถูกต้อง โปรดลองใหม่');
  return body as T;
}
