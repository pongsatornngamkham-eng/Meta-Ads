'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Activity, LockKeyhole, ArrowRight } from 'lucide-react';
import { requestJson } from '../../lib/api';

export default function Login(){
 const router=useRouter();
 const [username,setUsername]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[configured,setConfigured]=useState<boolean|null>(null);
 useEffect(()=>{requestJson<{authenticated:boolean;configured:boolean}>('/api/auth/session',{cache:'no-store'}).then(s=>{setConfigured(s.configured);if(s.authenticated)router.replace('/');}).catch(e=>setError(e instanceof Error?e.message:'ติดต่อระบบไม่ได้'));},[router]);
 async function submit(event:React.FormEvent){event.preventDefault();setBusy(true);setError('');try{
  await requestJson('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});setPassword('');router.replace('/');
 }catch(e){setError(e instanceof Error?e.message:'เข้าสู่ระบบไม่สำเร็จ');}finally{setBusy(false);}}
 return <main className="login-page"><section className="login-card"><div className="login-brand"><span className="brand-icon"><Activity size={24}/></span><strong>adscope<span>.</span></strong></div><div className="login-lock"><LockKeyhole size={24}/></div><h1>เข้าสู่ Dashboard ของคุณ</h1><p>ข้อมูลโฆษณาส่วนตัว เข้าถึงได้เฉพาะเจ้าของบัญชี</p>
 {configured===false&&<div className="alert warning">ยังไม่ได้ตั้งค่าบัญชีเจ้าของ Dashboard กรุณาให้ผู้ติดตั้งระบบดำเนินการก่อน</div>}
 {error&&<div className="alert error" role="alert">{error}</div>}
 <form onSubmit={submit}><label>ชื่อผู้ใช้<input autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} maxLength={100} required/></label><label>รหัสผ่าน<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} maxLength={256} required/></label><button className="button primary" disabled={busy||configured!==true}>{busy?'กำลังเข้าสู่ระบบ…':'เข้าสู่ Dashboard'}<ArrowRight size={16}/></button></form><small>บัญชีนี้ใช้สำหรับ Dashboard ของคุณ</small></section></main>;
}
