# shop/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import ReverseUser, ShippingAddress, Payment, Order  # Import Order for payment choices
from django_countries.fields import CountryField
from django_countries.widgets import CountrySelectWidget

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
    """
    Form for collecting shipping address details.
    Includes a checkbox to save the address as default for the user.
    Country is fixed to Egypt.
    """
    country = forms.CharField(
        widget=forms.HiddenInput(),
        initial='EG'  # Egypt country code
    )

    save_as_default = forms.BooleanField(
        required=False,
        initial=False,
        label="Save this address as my default for future orders",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = ShippingAddress
        exclude = ('order', 'is_default')
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Full Name', 'class': 'form-control'}),
            'address_line1': forms.TextInput(attrs={'placeholder': 'Address Line 1', 'class': 'form-control'}),
            'address_line2': forms.TextInput(attrs={'placeholder': 'Address Line 2 (Optional)', 'class': 'form-control'}),
            'city': forms.TextInput(attrs={'placeholder': 'City', 'class': 'form-control'}),
            'state_province_region': forms.TextInput(attrs={'placeholder': 'State/Province/Region (Optional)', 'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'placeholder': 'Postal Code (Optional)', 'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'Phone Number', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['save_as_default', 'country']:
                field.widget.attrs.setdefault('class', 'form-control')


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
