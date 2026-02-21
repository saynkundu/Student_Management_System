# forms.py
from django import forms
from .models import Question, Option, QuestionPaper
from django.forms import inlineformset_factory

class QuestionPaperForm(forms.ModelForm):
    class Meta:
        model = QuestionPaper
        fields = ['title', 'num_questions']

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'marks']

class OptionForm(forms.ModelForm):
    class Meta:
        model = Option
        fields = ['text', 'is_correct']

OptionFormSet = inlineformset_factory(
    Question,
    Option,
    form=OptionForm,
    extra=4,
    can_delete=False,
    min_num=4,
    validate_min=True,
    max_num=4,
    validate_max=True
)
