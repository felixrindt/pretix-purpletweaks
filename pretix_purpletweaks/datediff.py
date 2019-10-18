import datetime
from collections import namedtuple
from typing import Union

import pytz
from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext_lazy as _

DateDiff = namedtuple('DateDiff', ['mode', 'days'])

class DateDiffWrapper:
    """
    This contains information on a date that is relative to an event or an order. This means
    that the underlying data is a number of days and a mode stating wether we are after the
    order or before the event.
    """

    def __init__(self, data):
        self.data = data

    def datetime(self, order) -> datetime.datetime:
        from pretix.base.models import SubEvent
        event = order.event
        tz = pytz.timezone(event.settings.timezone)
        if self.data.mode == 'after_order':
            new_date = order.datetime.astimezone(tz) + datetime.timedelta(days=self.data.days)
        else:  # before event
            if order.event.has_subevents:
                event = event.subevents.filter(id__in=order.positions.values_list('subevent', flat=True)).order_by('date_from').last()
            new_date = event.date_from.astimezone(tz) - datetime.timedelta(days=self.data.days)

        return new_date

    def to_string(self) -> str:
        return 'DATEDIFF/{}/{}/'.format(
            self.data.days,
            self.data.mode
        )

    @classmethod
    def from_string(cls, input: str):
        parts = input.split('/')
        data = DateDiff(
            days=int(parts[1]),
            mode=parts[2],
        )
        return DateDiffWrapper(data)

    def __len__(self):
        return len(self.to_string())


def date_diff_wrapper_from_string(input:str):
    parts = input.split('/')
    data = DateDiff(
        days=int(parts[1]),
        mode=parts[2],
    )
    return DateDiffWrapper(data)


class DateDiffWidget(forms.MultiWidget):
    template_name = 'pretix_purpletweaks/datediff.html'

    def __init__(self, *args, **kwargs):
        self.status_choices = kwargs.pop('status_choices')
        widgets = (
            forms.RadioSelect(choices=self.status_choices),
            forms.NumberInput(),
            forms.NumberInput(),
        )
        super().__init__(widgets=widgets, *args, **kwargs)

    def decompress(self, value):
        if not value:
            return ['unset', 0, 0]
        value = date_diff_wrapper_from_string(value)
        return [value.data.mode, value.data.days, value.data.days]

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx['required'] = self.status_choices[0][0] != 'unset'
        return ctx


class DateDiffField(forms.MultiValueField):
    def __init__(self, *args, **kwargs):
        status_choices = [
            ('after_order', _('Order')+':'),
            ('before_event', _('Event')+':'),
        ]
        if not kwargs.get('required', True):
            status_choices.insert(0, ('unset', _('Not set')))
        fields = (
            forms.ChoiceField(
                choices=status_choices,
                required=True
            ),
            forms.IntegerField(
                required=False
            ),
            forms.IntegerField(
                required=False
            ),
        )
        if 'widget' not in kwargs:
            kwargs['widget'] = DateDiffWidget(status_choices=status_choices)
        kwargs.pop('max_length', 0)
        kwargs.pop('empty_value', 0)
        super().__init__(
            fields=fields, require_all_fields=False, *args, **kwargs
        )


    def compress(self, data_list):
        if not data_list:
            return None
        if data_list[0] == 'unset':
            return None
        else:
            return DateDiffWrapper(DateDiff(
                mode=data_list[0],
                days=data_list[1 if data_list[0]=='after_order' else 2],
            )).to_string()

    def clean(self, value):
        if value[0] == 'after_order' and value[1] is None:
            raise ValidationError(self.error_messages['incomplete'])
        elif value[0] == 'before_event' and value[2] is None:
            raise ValidationError(self.error_messages['incomplete'])

        return super().clean(value)
