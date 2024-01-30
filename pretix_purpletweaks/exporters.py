from collections import OrderedDict
from datetime import timezone

import bleach
import dateutil.parser
from django import forms
from django.db.models import (
    Case,
    Exists,
    F,
    Max,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, NullIf
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.timezone import is_aware, make_aware, now
from django.utils.translation import (
    gettext as _,
    gettext_lazy,
    pgettext,
    pgettext_lazy,
)
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from pretix.base.exporter import BaseExporter, ListExporter
from pretix.base.models import (
    Checkin,
    InvoiceAddress,
    Order,
    OrderPosition,
    Question,
)
from pretix.base.settings import PERSON_NAME_SCHEMES
from pretix.base.templatetags.money import money_filter
from pretix.base.timeframes import (
    DateFrameField,
    resolve_timeframe_to_datetime_start_inclusive_end_exclusive,
)
from pretix.control.forms.widgets import Select2
from pretix.helpers.filenames import safe_for_filename
from pretix.helpers.iter import chunked_iterable
from pretix.helpers.templatetags.jsonfield import JSONExtract
from pretix.plugins.checkinlists.exporters import (
    PDFCheckinList,
    CBFlowable,
    TableTextRotate,
)
from pretix.plugins.reports.exporters import ReportlabExportMixin


class PortraitPDFCheckinList(PDFCheckinList):
    name = "purble overview"
    identifier = "purple_checkinlistpdf"
    verbose_name = gettext_lazy("Check-in list (Portrait PDF)")
    category = pgettext_lazy("export_category", "Check-in")
    description = gettext_lazy(
        "Download a PDF version of a check-in list that can be used to check people in at the "
        "event without digital methods."
    )
    numbered_canvas = True

    @property
    def pagesize(self):
        from reportlab.lib import pagesizes

        return pagesizes.portrait(pagesizes.A4)

    def get_story(self, doc, form_data):
        cl = self.event.checkin_lists.get(pk=form_data["list"])

        questions = list(
            Question.objects.filter(event=self.event, id__in=form_data["questions"])
        )

        headlinestyle = self.get_style()
        headlinestyle.fontSize = 15
        headlinestyle.fontName = "OpenSansBd"
        colwidths = [3 * mm, 8 * mm, 6 * mm] + [
            a * (doc.width - 8 * mm)
            for a in [0.12, 0.23, (0.25 if questions else 0.60)]
            + ([0.35 / len(questions)] * len(questions) if questions else [])
        ]
        tstyledata = [
            ("VALIGN", (0, 0), (-1, 0), "BOTTOM"),
            ("ALIGN", (2, 0), (2, 0), "CENTER"),
            ("VALIGN", (0, 1), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, 0), "OpenSansBd"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("TEXTCOLOR", (0, 0), (0, -1), "#990000"),
            ("FONTNAME", (0, 0), (0, -1), "OpenSansBd"),
        ]

        story = [
            Paragraph(cl.name, headlinestyle),
        ]
        if cl.subevent:
            story += [
                Spacer(1, 3 * mm),
                Paragraph(
                    "{} ({} {})".format(
                        cl.subevent.name,
                        cl.subevent.get_date_range_display(),
                        date_format(
                            cl.subevent.date_from.astimezone(self.timezone),
                            "TIME_FORMAT",
                        ),
                    ),
                    self.get_style(),
                ),
            ]

        story += [Spacer(1, 5 * mm)]

        tdata = [
            [
                "",
                "",
                # Translators: maximum 5 characters
                TableTextRotate(pgettext("tablehead", "paid")),
                _("Order"),
                _("Name"),
                _("Product") + " / " + _("Price"),
            ],
        ]

        headrowstyle = self.get_style()
        headrowstyle.fontName = "OpenSansBd"
        for q in questions:
            txt = str(q.question)
            p = Paragraph(txt, headrowstyle)
            while p.wrap(colwidths[len(tdata[0])], 5000)[1] > 30 * mm:
                txt = txt[: len(txt) - 50] + "..."
                p = Paragraph(txt, headrowstyle)
            tdata[0].append(p)

        qs = self._get_queryset(cl, form_data)

        for op in qs:
            try:
                ian = op.order.invoice_address.name
                iac = op.order.invoice_address.company
            except:
                ian = ""
                iac = ""

            name = (
                op.attendee_name
                or (op.addon_to.attendee_name if op.addon_to else "")
                or ian
            )
            if iac:
                name += "<br/>" + iac

            payment = op.order.payments.first()
            if not payment:
                payment_provider_name = ""
            elif payment.payment_provider.identifier == "free":
                payment_provider_name = ""
            else:
                payment_provider_name = (
                    payment.payment_provider.public_name if payment else ""
                )
            if payment_provider_name:
                item = "{} ({}, {})".format(
                    str(op.item)
                    + (" – " + str(op.variation.value) if op.variation else ""),
                    money_filter(op.price, self.event.currency),
                    payment_provider_name,
                )
            else:
                item = "{} ({})".format(
                    str(op.item)
                    + (" – " + str(op.variation.value) if op.variation else ""),
                    money_filter(op.price, self.event.currency),
                )

            if self.event.has_subevents and not cl.subevent:
                item += "<br/>{} ({})".format(
                    op.subevent.name,
                    date_format(
                        op.subevent.date_from.astimezone(self.event.timezone),
                        "SHORT_DATETIME_FORMAT",
                    ),
                )
            if op.seat:
                item += "<br/>" + str(op.seat)
            name = bleach.clean(str(name), tags=["br"]).strip().replace("<br>", "<br/>")
            if op.blocked:
                name = '<font face="OpenSansBd">[' + _("Blocked") + "]</font> " + name
            row = [
                "!!" if op.require_checkin_attention else "",
                CBFlowable(bool(op.last_checked_in)) if not op.blocked else "—",
                "✘" if op.order.status != Order.STATUS_PAID else "✔",
                op.order.code,
                Paragraph(name, self.get_style()),
                Paragraph(
                    bleach.clean(str(item), tags=["br"])
                    .strip()
                    .replace("<br>", "<br/>"),
                    self.get_style(),
                ),
            ]
            acache = {}
            if op.addon_to:
                for a in op.addon_to.answers.all():
                    # We do not want to localize Date, Time and Datetime question answers, as those can lead
                    # to difficulties parsing the data (for example 2019-02-01 may become Février, 2019 01 in French).
                    if a.question.type in Question.UNLOCALIZED_TYPES:
                        acache[a.question_id] = a.answer
                    else:
                        acache[a.question_id] = str(a)
            for a in op.answers.all():
                # We do not want to localize Date, Time and Datetime question answers, as those can lead
                # to difficulties parsing the data (for example 2019-02-01 may become Février, 2019 01 in French).
                if a.question.type in Question.UNLOCALIZED_TYPES:
                    acache[a.question_id] = a.answer
                else:
                    acache[a.question_id] = str(a)
            for q in questions:
                txt = acache.get(q.pk, "")
                txt = bleach.clean(txt, tags=["br"]).strip().replace("<br>", "<br/>")
                p = Paragraph(txt, self.get_style())
                while p.wrap(colwidths[len(row)], 5000)[1] > 50 * mm:
                    txt = txt[: len(txt) - 50] + "..."
                    p = Paragraph(txt, self.get_style())
                row.append(p)
            if op.order.status != Order.STATUS_PAID:
                tstyledata += [
                    ("BACKGROUND", (2, len(tdata)), (2, len(tdata)), "#990000"),
                    ("TEXTCOLOR", (2, len(tdata)), (2, len(tdata)), "#ffffff"),
                    ("ALIGN", (2, len(tdata)), (2, len(tdata)), "CENTER"),
                ]
            if op.blocked:
                tstyledata += [
                    ("BACKGROUND", (1, len(tdata)), (1, len(tdata)), "#990000"),
                    ("TEXTCOLOR", (1, len(tdata)), (1, len(tdata)), "#ffffff"),
                    ("ALIGN", (1, len(tdata)), (1, len(tdata)), "CENTER"),
                ]
            tdata.append(row)

        table = Table(tdata, colWidths=colwidths, repeatRows=1)
        table.setStyle(TableStyle(tstyledata))
        story.append(table)
        return story
