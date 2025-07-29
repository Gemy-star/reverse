# shop/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import ReverseUser, ShippingAddress, Payment, Order  # Import Order for payment choices
from django.utils.translation import gettext_lazy as _

class RegisterForm(UserCreationForm):
    """
    Form for user registration, extending Django's built-in UserCreationForm.
    Includes custom fields from ReverseUser model.
    """
    phone = forms.CharField(
        max_length=15,
        required=False,
        help_text="Optional: Your phone number (e.g., +1234567890)"
    )
    is_customer = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.HiddenInput(),
        help_text="Indicates if the user is a customer."
    )

    class Meta(UserCreationForm.Meta):
        model = ReverseUser
        fields = UserCreationForm.Meta.fields + ('phone', 'is_customer',)
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Username', 'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            if field_name != 'password2':  # password2 uses default widget styling
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})


class LoginForm(AuthenticationForm):
    """
    Standard Django form for user authentication.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Username or Email', 'class': 'form-control'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password', 'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].required = True
        self.fields['password'].required = True
class ShippingAddressForm(forms.ModelForm):
    class Meta:
        model = ShippingAddress
        fields = [
            'full_name', 'address_line1', 'address_line2', 'city', 'phone_number', 'is_default' , 'email'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Full Name')}),
            'address_line1': forms.Textarea(attrs={'class': 'form-control', 'placeholder': _('Address Line 1')}),
            'address_line2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Address Line 2 (Optional)')}),
            'city': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Enter your email')}),

            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Phone Number')}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'full_name': _('Full Name'),
            'address_line1': _('Address Line 1'),
            'address_line2': _('Address Line 2'),
            'city': _('City'),
            'phone_number': _('Phone Number'),
            'is_default': _('Set as default address'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply 'form-control' class to all fields if not already set
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
        # Ensure choices are localized
        self.fields['city'].choices = ShippingAddress.CITY_CHOICE


class PaymentForm(forms.Form):
    PAYMENT_CHOICES = [
        ('cod', 'Cash on Delivery'),
        # ('visa', 'Visa (Coming Soon)'),  # Uncomment to add Visa later
    ]

    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Select Payment Method"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment_method'].widget.attrs.update({'class': 'form-check-input'})
