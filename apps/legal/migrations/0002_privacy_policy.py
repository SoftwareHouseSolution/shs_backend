"""The privacy policy as first published (27 October 2026). Created only when there is none
yet, so it never overwrites an edited version; editable afterwards in Admin → Legal pages."""

import datetime

from django.db import migrations

TITLE_AR = "سياسة الخصوصية"
TITLE_EN = "Privacy Policy"

BODY_AR = """## ١. من نحن

تنشر هذه السياسة **SWHS**، ويُشار إليها فيما يلي بـ «نحن».

القاهرة، مصر
للتواصل: [صفحة التواصل على موقعنا](/ar#contact)

## ٢. على ماذا تسري هذه السياسة

تسري على كل ما نقدّمه، وليس على منتج بعينه: تطبيقاتنا المنشورة على Google Play و App Store — ومنها **My Jewelry** — وموقعنا الإلكتروني، والأنظمة التي نطوّرها لعملائنا.

## ٣. بياناتك تبقى لديك

أنظمتنا تُشغَّل لدى كل عميل على نظامه الخاص، والتطبيق واجهة لذلك النظام. فالبيانات التي ينشئها المستخدم أثناء عمله تذهب إلى نظام الجهة التي يعمل بها، **ولا تُرسل إلينا ولا إلى أي جهة ثالثة**.

ولذلك فإن العميل هو مالك تلك البيانات والمتحكم فيها والمسؤول عنها، وسياسة الخصوصية الخاصة به هي التي تحكمها. أما نحن فلا نحتفظ بنسخة منها ولا نملك صلاحية الاطّلاع عليها.

## ٤. ما تتعامل معه تطبيقاتنا

- **بيانات الدخول:** اسم المستخدم وكلمة المرور، وتُستخدم للتحقق من الهوية لدى نظام الجهة التي يعمل بها المستخدم، ولا غير ذلك.
- **بيانات العمل** التي يُدخلها المستخدم أو يقرؤها أثناء استخدامه، وتذهب إلى نظام تلك الجهة وحده.
- **الكاميرا:** تُستخدم لقراءة الرموز المطبوعة على القطع والمستندات. تُقرأ الصورة في حينها ثم تُهمَل فورًا — لا تُحفَظ، ولا تُرسَل، ولا نطّلع عليها.

ويحتفظ التطبيق على الجهاز ببيانات الجلسة وتفضيلات المستخدم فقط، في تخزين مؤمَّن. **ولا تُحفَظ كلمة المرور على الجهاز إطلاقًا.**

تطبيقاتنا **لا تطلب** الموقع الجغرافي، ولا جهات الاتصال، ولا الصور المحفوظة، ولا الميكروفون.

وعند إرسال مستند من التطبيق، يختار المستخدم بنفسه وسيلة الإرسال والجهة التي يرسل إليها. ولا يرسل التطبيق شيئًا من تلقاء نفسه. وبمجرد خروج الملف إلى تطبيق آخر تصبح سياسة ذلك التطبيق هي الحاكمة، لا سياستنا.

## ٥. موقعنا الإلكتروني

تصفّح الموقع لا يتطلب حسابًا. وتُسجَّل بيانات تقنية أساسية مع كل طلب — كعنوان IP ونوع المتصفح ووقت الطلب — وتُستخدم لتشغيل الموقع وتأمينه فقط.

وإذا راسلتنا، نحتفظ بما أرسلته للمدة اللازمة للردّ عليك ومتابعة طلبك، ولا نستخدمه لغرض آخر ولا نشاركه مع أحد.

## ٦. ما لا نفعله

- لا نبيع بياناتك ولا نشاركها مع أي جهة ثالثة.
- لا نستخدم إعلانات ولا أدوات تتبُّع.
- لا نتابع سلوك المستخدم داخل تطبيقاتنا.
- لا نجمع تقارير أعطال تلقائيًا؛ ولا يُرسَل إلينا شيء من ذلك إلا إذا اختار المستخدم إرساله بنفسه عند طلب الدعم الفني.

## ٧. مدة الحفظ والحذف

**على الجهاز:** حذف التطبيق يمحو كل ما يحتفظ به على الهاتف. وتسجيل الخروج يُنهي الجلسة.

**لدى الجهة التي تعمل بها:** مدة الحفظ والحذف من اختصاصها، فهي مالكة البيانات. والحسابات يُنشئها ويحذفها مدير النظام لديها، ولا يمكن إنشاء حساب من داخل التطبيق. فمن أراد حذف حسابه أو بياناته فمرجعه إدارة تلك الجهة، ونحن لا نملك صلاحية الحذف لديها.

**لدينا:** مراسلاتك تُحذف عندما ينتهي الغرض منها، أو متى طلبت ذلك عبر [صفحة التواصل](/ar#contact).

## ٨. أمان البيانات

نستخدم وسائل حماية متعارفًا عليها في هذا المجال: تشفير الاتصال في الإعداد القياسي، وتخزين مؤمَّن لبيانات الجلسة على الجهاز، وصلاحيات تُفرَض على مستوى النظام نفسه فلا يصل المستخدم إلى ما لا يُصرَّح له به.

وقد يختار العميل تشغيل نظامه داخل شبكته الخاصة بإعداد يختلف عن الإعداد القياسي؛ وهذا قرار يخصّه ويقع ضمن مسؤوليته عن شبكته.

## ٩. الأطفال

منتجاتنا أدوات عمل موجّهة للشركات والعاملين بها، وغير موجّهة لمن هم أقل من ١٨ عامًا، ولا نجمع بيانات أطفال عن علم.

## ١٠. تغييرات هذه السياسة

إذا تغيّرت طريقة تعاملنا مع البيانات نحدّث هذه الصفحة ونغيّر تاريخ «آخر تحديث» أعلاها. ويظل الإصدار المنشور هنا هو الإصدار السارى.

## ١١. للتواصل

لأي سؤال عن الخصوصية، أو لطلب حذف ما نحتفظ به من مراسلاتك، تواصل معنا عبر [صفحة التواصل على موقعنا](/ar#contact)."""

BODY_EN = """## 1. Who we are

This policy is published by **SWHS** ("we").

Cairo, Egypt
Contact: [the contact page on our website](/en#contact)

## 2. What this policy covers

Everything we offer, rather than any one product: our applications published on Google Play and the App Store — including **My Jewelry** — our website, and the systems we build for our customers.

## 3. Your data stays with you

Our systems run on each customer's own system, and the application is a front end for it. Data a user creates while working goes to the system of the organisation they work for, and **is not sent to us or to any third party**.

The customer therefore owns that data, controls it and is responsible for it, and the customer's own privacy policy governs it. We keep no copy of it and have no access to it.

## 4. What our applications handle

- **Sign-in details:** a username and password, used to verify identity against the system of the organisation the user works for, and for nothing else.
- **Business data** the user enters or reads while working, which goes to that organisation's system alone.
- **The camera:** used to read the codes printed on items and documents. The image is read at that moment and immediately discarded — it is not stored, not transmitted, and not seen by us.

On the device, the application keeps only session data and user preferences, in protected storage. **The password is never stored on the device.**

Our applications do **not** request location, contacts, stored photos, or the microphone.

When a document is sent from the application, the user chooses the means and the recipient. The application sends nothing on its own. Once the file leaves for another application, that application's policy governs it, not ours.

## 5. Our website

Browsing the site needs no account. Basic technical data is logged with each request — such as IP address, browser type and the time of the request — and is used only to operate and secure the site.

If you write to us, we keep what you sent for as long as it takes to answer you and follow up, use it for nothing else, and share it with no one.

## 6. What we do not do

- We do not sell your data or share it with any third party.
- We use no advertising and no tracking.
- We do not monitor user behaviour inside our applications.
- We do not collect crash reports automatically; nothing of the kind reaches us unless the user chooses to send it when asking for support.

## 7. Retention and deletion

**On the device:** uninstalling the application erases everything it keeps on the phone. Signing out ends the session.

**With the organisation you work for:** retention and deletion are theirs to decide, as the owner of the data. Accounts are created and deleted by their own administrator, and an account cannot be created from within the application. Anyone wanting their account or data deleted should therefore go to that organisation's management; we have no deletion rights there.

**With us:** your correspondence is deleted when its purpose has passed, or whenever you ask us through the [contact page](/en#contact).

## 8. Security

We use protections that are standard in this field: encryption of the connection in the standard configuration, protected storage for session data on the device, and permissions enforced by the system itself, so a user cannot reach what they are not authorised to.

A customer may choose to run their system inside their own network with a configuration that differs from the standard one; that is their decision and falls within their responsibility for their network.

## 9. Children

Our products are business tools for companies and their staff. They are not directed to anyone under 18, and we do not knowingly collect children's data.

## 10. Changes to this policy

If the way we handle data changes, we will update this page and change the "Last updated" date above. The version published here is the version in force.

## 11. Contact

For any privacy question, or to ask us to delete correspondence we hold, reach us through [the contact page on our website](/en#contact)."""


def create_privacy_policy(apps, schema_editor):
    LegalDocument = apps.get_model("legal", "LegalDocument")
    if LegalDocument.objects.filter(slug="privacy").exists():
        return
    LegalDocument.objects.create(
        slug="privacy",
        title=TITLE_EN,
        title_en=TITLE_EN,
        title_ar=TITLE_AR,
        body=BODY_EN,
        body_en=BODY_EN,
        body_ar=BODY_AR,
        last_updated=datetime.date(2026, 10, 27),
        is_published=True,
        show_in_footer=True,
    )


class Migration(migrations.Migration):
    dependencies = [("legal", "0001_initial")]

    operations = [migrations.RunPython(create_privacy_policy, migrations.RunPython.noop)]
