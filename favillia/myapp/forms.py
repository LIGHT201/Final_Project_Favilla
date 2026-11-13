from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Customer


class CustomerSignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=False)
    delivery_address = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "phone", "delivery_address")

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Customer.objects.create(
                user=user,
                phone=self.cleaned_data["phone"],
                delivery_address=self.cleaned_data["delivery_address"],
            )
        return user
