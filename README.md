# Rawaj — واجهة المطعم والإيجنتات عبر FastAPI

المشروع يحتوي الآن واجهة React في `frontend/` مرتبطة بالباك الحالي. ابدأ من تسجيل الدخول التجريبي، ثم اختر مطعمك أو أضف مطعمًا من الرئيسية. القائمة الجانبية تحتوي **Home** و**Monthly Strategy** و**Content Creation** فقط؛ الكالندر ضمن صفحة الخطة الشهرية.

## فتح الواجهة

من مجلد المشروع:

```powershell
python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

افتح **[واجهة Rawaj](http://127.0.0.1:8000/#/sign-in)**. توثيق الـAPI موجود منفصلًا على [صفحة docs](http://127.0.0.1:8000/docs). إذا كان الباك يعمل مسبقًا، ابنِ الفرونت ثم حدّث صفحة المتصفح.

تسجيل الدخول **واجهة تجريبية فقط** حسب نطاق الطلب: اضغط `Fill demo details` ثم `Sign in`، أو أدخل بريدًا صالحًا وكلمة تجريبية من 6 أحرف على الأقل. لا يتم إرسال كلمة المرور أو حفظها، ولا تُنشأ حسابات أو جلسة مصادقة في الباك. زر `Sign out` يمسح حالة الدخول التجريبية في التبويب. يلزم إضافة مصادقة حقيقية قبل إتاحة المشروع للعامة.

تستخدم الواجهة نفس عنوان FastAPI، وتبقى جميع إعدادات الباك ومفاتيح الخدمات في **ملف `.env` واحد في جذر المشروع**. لا يوجد ملف بيئة ثانٍ للفرونت، ولم يُستخدم الباك أو ملف البيئة المرفق داخل ZIP الواجهة.

## الصفحات والكونتكست

- **Home:** اختيار المطعم، إضافة مطعم أو مقهى، وتعديل الاسم والنوع والموقع والقائمة الفعلية والجمهور والأهداف ونبرة المحتوى ولغته. تُحفظ هذه البيانات في الباك، ويمكن تشغيل البحث والتأهيل من زر `Analyze Instagram`.
- **Monthly Strategy:** خطة تعتمد على الكونتكست المحفوظ والفجوات التسويقية المتوفرة. الخطة الحالية مبنية بقوالب مرتبطة بالبيانات، ولا تُقدَّم كخطة مولَّدة بالذكاء الاصطناعي. الكالندر يحسب أيام الشهر وأيام الأسبوع الصحيحة، ويدعم تغيير الشهر وإضافة مهمة وتحديد إكمالها.
- **Content Creation:** اختيار مهمة من خطة المطعم، ثم طلب ثلاثة اقتراحات بالذكاء الاصطناعي باستخدام الكونتكست والمهمة المحفوظين في الباك. يمكن إعادة التوليد مع ملاحظات، وحفظ الفكرة المختارة للمهمة واسترجاعها بعد تحديث الصفحة.

تُحفظ الخطط والمهام والأفكار حسب المطعم والشهر. تعديل الكونتكست المؤثر ينشئ نسخة جديدة كي لا تختلط أفكار الاسم أو نوع المطعم القديم بالبيانات الجديدة؛ النسخ السابقة تبقى في قاعدة البيانات. لا يُستدعى مزود الذكاء الاصطناعي تلقائيًا عند فتح الصفحات؛ البحث وتوليد الأفكار يبدأان بأزرارهما المخصصة.

## تطوير الفرونت

لتشغيل تحديثات React مباشرة أثناء التطوير، اترك FastAPI يعمل على `8000` وافتح طرفية أخرى:

```powershell
npm --prefix frontend run dev
```

افتح [Vite على المنفذ 5173](http://127.0.0.1:5173). إعداد [Vite proxy](https://vite.dev/config/server-options#server-proxy) يمرر `/api` إلى FastAPI. بعد التعديلات أعد `npm --prefix frontend run build` لتحديث النسخة التي يقدمها FastAPI عبر [StaticFiles](https://fastapi.tiangolo.com/tutorial/static-files/).

## التشغيل على Windows

من PowerShell داخل مجلد المشروع، أنشئ بيئة Python وفعّلها إذا لم تكن لديك بيئة جاهزة:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

استخدم ملف `.env` الموجود في جذر المشروع لجميع الإيجنتات وتوليد المحتوى. أضف الإعدادات الناقصة إلى نفس الملف.

المتغيرات المطلوبة لتشغيل التحليل:

```dotenv
OPENAI_API_KEY=your_openai_key
APIFY_API_TOKEN=your_apify_token
TAVILY_API_KEY=your_tavily_key
```

حدد عنوان واجهتك في `FRONTEND_ORIGINS`. القيم الافتراضية تسمح بالمضيفين `localhost` و`127.0.0.1` على المنفذين `3000` و`5173`:

```dotenv
FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173
```

العنوان يتكون من البروتوكول والمضيف والمنفذ، دون مسار أو شرطة مائلة في النهاية. إذا تغيّر منفذ الفرونت، عدّل المتغير ثم أعد تشغيل الباك. راجع [شرح CORS في FastAPI](https://fastapi.tiangolo.com/tutorial/cors/) لتفاصيل إعداد الأصول المسموحة.

قاعدة البيانات الافتراضية هي `rawaj.db` الموجودة في جذر المشروع، ويُحسب مسارها المطلق تلقائيًا. يمكنك اختيار قاعدة أخرى عبر `DATABASE_URL`، مثل:

```dotenv
DATABASE_URL=sqlite:///D:/my-project/data/rawaj.db
```

شغّل الباك:

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

افتح [توثيق API التفاعلي](http://127.0.0.1:8000/docs) لتجربة الطلبات. الواجهة ترسل الطلبات إلى `http://127.0.0.1:8000`.

## الربط من الفرونت

الواجهة المرفقة تستخدم `frontend-integration/rawaj-api.js` بالفعل؛ ويمكن استيراده في واجهة إضافية. يعمل العميل مع JavaScript وReact وVue وغيرهما، باستخدام `fetch` في المتصفح.

```javascript
import { createRawajClient } from "./rawaj-api.js";

const api = createRawajClient({ baseUrl: "http://127.0.0.1:8000" });

// استبدل هذه القيم بمدخلات نموذج المطعم في واجهتك.
const restaurant = await api.createRestaurant({
  name: "مطعم المثال",
  instagram_username: "example_restaurant",
  email: "hello@example.com",
  location: "الرياض",
  context: {
    cuisine: "إيطالي",
    target_audience: "العائلات",
    goals: ["زيادة الحجوزات", "تحسين محتوى إنستغرام"],
    notes: "نركّز على العشاء وعطلة نهاية الأسبوع",
  },
});

// احفظ restaurant.id في حالة واجهتك، واستخدمه لجميع طلبات هذا المطعم.
const restaurantId = restaurant.id;
const saved = await api.getRestaurant(restaurantId);
const currentContext = await api.getRestaurantContext(restaurantId);
console.log(saved, currentContext);

const controller = new AbortController();

try {
  const job = await api.analyzeRestaurant(restaurantId, {
    content_limit: 30,
    lookback_days: 90,
    force_refresh: false,
    signal: controller.signal,
  });

  await api.waitForJob(job.id, {
    signal: controller.signal,
    onUpdate: (currentJob) => {
      // اعرض queued / running / completed / failed في واجهتك.
      console.log(currentJob.status);
    },
  });

  const context = await api.getRestaurantContext(restaurantId, {
    signal: controller.signal,
  });

  console.log(context.research?.result);
  console.log(context.qualification?.result);
} catch (error) {
  if (error.name === "AbortError") {
    console.log("توقفت متابعة المهمة في الواجهة");
  } else {
    console.error(error.message);
  }
}

// عند مغادرة الصفحة أو إلغاء المتابعة: controller.abort();
// هذا يوقف طلبات الواجهة؛ المهمة الموجودة على السيرفر تستمر.
```

`context` كائن JSON حر لحفظ معلومات المطعم الإضافية من واجهتك. يستلمه Qualification Agent مع نتائج البحث، بينما يعتمد Research Agent على بيانات المطعم الأساسية. عدّل البيانات أو الكونتكست أولًا، ثم اطلب تحليلًا جديدًا إذا أردت نتيجة تعكس التعديلات.

كل طلب تحليل عبر API يشغّل تأهيلًا جديدًا باستخدام الكونتكست المحفوظ، حتى إذا كان فارغًا. يمكن إعادة استخدام بحث محفوظ يطابق `content_limit` و`lookback_days`؛ استخدم `force_refresh: true` لإجراء بحث جديد أيضًا. يقبل `content_limit` عددًا صحيحًا من 1 إلى 100، و`lookback_days` عددًا صحيحًا من 1 إلى 365.

يمكن تحميل المطاعم الموجودة بدل إنشاء مطعم في كل مرة:

```javascript
const { items, total } = await api.listRestaurants({ offset: 0, limit: 50 });

// أرسل كائن الكونتكست الكامل الذي تريد حفظه.
await api.updateRestaurant(restaurantId, {
  location: "جدة",
  context: {
    cuisine: "إيطالي",
    target_audience: "العائلات",
    goals: ["زيادة طلبات التوصيل"],
  },
});

// بعد نجاح التأهيل، أنشئ مسودة للتواصل لعرضها في واجهتك.
const draft = await api.createOutreachDraft(restaurantId);
console.log(draft.subject, draft.body, draft.message_type);
```

تقبل عمليات العميل `signal` لإلغاء طلبات `fetch`: داخل كائن الخيارات في `listRestaurants` و`analyzeRestaurant` و`waitForJob`، أو كوسيط خيارات أخير في بقية الدوال.

`waitForJob` يتابع كل ثانيتين بمهلة افتراضية 15 دقيقة. يرجع المهمة عند `completed`، ويرمي `RawajJobError` عند `failed` مع تفاصيل المهمة في `error.job`. انتهاء المهلة ينتج خطأ باسم `TimeoutError`، ويمكن مواصلة الاستعلام بنفس معرّف المهمة عبر `getJob` أو `waitForJob`؛ لا تحتاج إنشاء تحليل آخر لهذا السبب. أخطاء HTTP تكون `RawajApiError` وبداخلها `status` و`detail` لعرض رسالة مناسبة في واجهتك.

## مسارات API

| الطلب | المسار | الاستخدام |
| --- | --- | --- |
| `GET` | `/api/restaurants?offset=0&limit=50` | قائمة `{items, total, offset, limit}` |
| `POST` | `/api/restaurants` | إنشاء مطعم مع `name` و`instagram_username` وبياناته الاختيارية |
| `GET` | `/api/restaurants/{id}` | بيانات مطعم |
| `PATCH` | `/api/restaurants/{id}` | تعديل `name`, `email`, `location`, `is_active`, `context` |
| `GET` | `/api/restaurants/{id}/context` | بيانات المطعم ونتائج البحث والتأهيل المرتبطة وآخر مهمة |
| `POST` | `/api/restaurants/{id}/analyze` | بدء تحليل؛ يرجع `202` ومهمة لها `id` |
| `GET` | `/api/jobs/{id}` | متابعة حالة المهمة |
| `POST` | `/api/restaurants/{id}/outreach/draft` | إنشاء `{subject, body, message_type}` |

لا يدعم التعديل تغيير `instagram_username`. استجابة المطعم تشمل أيضًا `id`, `instagram_url`, `is_active`, `created_at`, `updated_at`, `context`.

عند توفر نتائج لآخر مهمة تحليل، يرجع مسار الكونتكست البحث والتأهيل المشار إليهما في تلك المهمة تحديدًا؛ قد يكون البحث أقدم من أحدث بحث محفوظ إذا أعادت المهمة استخدام بحث يطابق إعداداتها. عند غياب مرجع بحث للمهمة، يعرض المسار أحدث بحث محفوظ وتأهيله المطابق. اعتمد على `latest_job.status` لمعرفة ما إذا كان التحليل المطلوب قد انتهى.

يرجع مسار الكونتكست الشكل التالي؛ تكون نتائج البحث والتأهيل والمهمة `null` قبل توفرها:

```javascript
{
  restaurant: { /* بيانات المطعم والكونتكست المحفوظ */ },
  research: { id, status, created_at, result },
  qualification: { id, research_run_id, status, created_at, result },
  latest_job: { id, restaurant_id, status /* وبيانات المهمة */ }
}
```

المهمة تحتفظ بخيارات `content_limit`, `lookback_days`, `force_refresh`، وأوقات `created_at`, `started_at`, `finished_at`، ومعرّفات `research_run_id`, `qualification_run_id`، ورسالة `error` عند الفشل. حالات المهمة هي `queued` ثم `running` ثم `completed` أو `failed`.

## الاختبارات وحدود التشغيل

شغّل اختبارات الربط بعد تثبيت اعتماديات الاختبار:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

التشغيل الحالي مخصص للتطوير المحلي بعملية سيرفر واحدة، ولا يتضمن مصادقة للمستخدمين؛ أبقه على `127.0.0.1` إلى أن تُضاف حماية الوصول المناسبة للنشر. المهام تعمل داخل عملية الباك باستخدام [BackgroundTasks في FastAPI](https://fastapi.tiangolo.com/tutorial/background-tasks/). إعادة التشغيل، بما فيها إعادة التحميل عند تعديل الملفات، تقطع التحليل الجاري، وتُعلَّم المهام غير المنتهية كـ`failed` عند بدء السيرفر مجددًا. اطلب تحليلًا جديدًا لهذه المهام. لتشغيل إنتاجي بعدة عمليات، يحتاج تنفيذ المهام إلى عامل وطابور مستقلين.

التحليل يستخدم خدمات OpenAI وApify وTavily حسب المفاتيح المتوفرة لديك. مسار التواصل ينشئ مسودة فقط ولا يرسل بريدًا إلكترونيًا.

## API التخطيط والمحتوى

| الطلب | المسار | الاستخدام |
| --- | --- | --- |
| `GET` | `/api/restaurants/{id}/strategy?month=YYYY-MM` | الخطة الحالية؛ `404` إذا لم توجد خطة مطابقة للكونتكست |
| `POST` | `/api/restaurants/{id}/strategy` | إنشاء أو استرجاع خطة ببيانات `{month, regenerate:false}` |
| `POST` | `/api/restaurants/{id}/strategy/tasks` | إضافة مهمة `{month,date,title,type,objective}` |
| `PATCH` | `/api/restaurants/{id}/strategy/tasks/{task_id}` | حفظ `status` أو `saved_idea` مع `month` |
| `POST` | `/api/restaurants/{id}/content-ideas` | توليد أفكار عبر `{month,task_id,previous_ideas,feedback}` |

توليد المحتوى يستخدم `OPENAI_API_KEY` من نفس `.env`، ويمكن اختيار النموذج اختياريًا باستخدام `RAWAJ_IDEA_MODEL`. يُرجع `503` إذا لم يُضبط المفتاح و`502` إذا فشل المزود، دون تسريب رسالة المزود الخام أو المفتاح.

اختبار المتصفح موجود في `tests/frontend-smoke.mjs` ويستخدم Chrome مثبّتًا محليًا وNode. شغّله فقط مقابل سيرفر بقاعدة اختبار مؤقتة؛ فهو يضيف ويعدّل مطعمًا تجريبيًا ويحاكي طلبات أفكار المحتوى لتجنب استخدام الخدمات المدفوعة. اختبارات Python تعمل تلقائيًا على قواعد مؤقتة.
