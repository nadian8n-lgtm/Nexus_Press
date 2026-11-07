import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getFirestore, collection, addDoc, doc, getDoc, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { firebaseConfig } from "./firebase-config.js";

const $ = (id) => document.getElementById(id);
const say = (el, text, cls) => { el.className = "notice " + (cls || ""); el.textContent = text; };
const STATUS = { new: "تم استلام رسالتك وهي قيد المراجعة", read: "تمت قراءة رسالتك وسنرد عليك قريباً", replied: "تم الرد على رسالتك" };

const configured = firebaseConfig.apiKey && !String(firebaseConfig.apiKey).startsWith("PASTE");

if (!configured) {
  $("contact-box").innerHTML = '<p class="notice err">نموذج الاتصال قيد الإعداد حالياً، يرجى المحاولة لاحقاً.</p>';
} else {
  const db = getFirestore(initializeApp(firebaseConfig));

  $("cf").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const out = $("cf-msg");
    if ($("c-web").value) { say(out, "تم الإرسال.", "ok"); ev.target.reset(); return; } // honeypot (spam bots)
    const name = $("c-name").value.trim(), email = $("c-email").value.trim();
    const subject = $("c-subject").value.trim(), message = $("c-message").value.trim();
    if (name.length < 2 || subject.length < 2) return say(out, "يرجى كتابة الاسم والموضوع.", "err");
    if (message.length < 10) return say(out, "الرسالة قصيرة جداً (10 أحرف على الأقل).", "err");
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return say(out, "صيغة البريد الإلكتروني غير صحيحة.", "err");
    const btn = ev.target.querySelector("button");
    btn.disabled = true;
    say(out, "جارٍ الإرسال…");
    try {
      const ref = await addDoc(collection(db, "messages"), {
        name, email, subject, message, status: "new", reply: "", createdAt: serverTimestamp()
      });
      out.className = "notice ok";
      out.textContent = "تم إرسال رسالتك بنجاح. احتفظ برمز المتابعة التالي لقراءة ردنا: ";
      const code = document.createElement("code");
      code.className = "ticket";
      code.textContent = ref.id;
      out.appendChild(code);
      ev.target.reset();
      $("t-id").value = ref.id;
    } catch (e) {
      console.error(e);
      say(out, "تعذر إرسال الرسالة الآن، يرجى المحاولة لاحقاً.", "err");
    } finally {
      btn.disabled = false;
    }
  });

  $("tf").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const out = $("tf-msg"), id = $("t-id").value.trim();
    if (!/^[A-Za-z0-9]{20}$/.test(id)) return say(out, "رمز المتابعة غير صحيح (20 حرفاً).", "err");
    say(out, "جارٍ البحث…");
    try {
      const snap = await getDoc(doc(db, "messages", id));
      if (!snap.exists()) return say(out, "لم نجد رسالة بهذا الرمز.", "err");
      const d = snap.data();
      out.className = "notice ok";
      out.textContent = "";
      const lines = ["الموضوع: " + d.subject, "الحالة: " + (STATUS[d.status] || d.status)];
      lines.forEach((t) => { const p = document.createElement("p"); p.textContent = t; out.appendChild(p); });
      if (d.reply) {
        const h = document.createElement("p"); h.innerHTML = "<b>ردّنا:</b>"; out.appendChild(h);
        const r = document.createElement("p"); r.className = "reply"; r.textContent = d.reply; out.appendChild(r);
      }
    } catch (e) {
      console.error(e);
      say(out, "تعذر جلب الحالة الآن، يرجى المحاولة لاحقاً.", "err");
    }
  });
}
