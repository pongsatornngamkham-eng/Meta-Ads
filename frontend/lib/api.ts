const CONNECTION_ERROR = 'ติดต่อระบบ FastAPI ไม่ได้ โปรดเปิด backend ที่พอร์ต 8000 แล้วลองอีกครั้ง';

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
      throw new Error('รอนานเกิน 20 วินาที โปรดตรวจว่า backend และ PostgreSQL พร้อมใช้งาน แล้วลองใหม่');
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
    if (typeof detail === 'string' && response.status < 500) throw new Error(detail);
    if (response.status === 503 && typeof detail === 'string') {
      throw new Error('ฐานข้อมูลยังไม่พร้อม โปรดเปิด Docker Desktop แล้วรัน docker compose up -d db และขั้นตอน init ฐานข้อมูลใน README-WINDOWS.md');
    }
    if (response.status === 422) throw new Error('ข้อมูลไฟล์ไม่ถูกต้อง โปรดใช้ CSV ตามไฟล์ตัวอย่าง');
    throw new Error(`ระบบประมวลผลไม่สำเร็จ (HTTP ${response.status}) โปรดตรวจหน้าต่าง backend แล้วลองใหม่`);
  }
  if (typeof body !== 'object' || body === null) throw new Error('ระบบตอบกลับในรูปแบบไม่ถูกต้อง โปรดลองใหม่');
  return body as T;
}
