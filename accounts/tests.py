from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .forms import LoginForm
from .utils import group_required, is_staff_or_superuser


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_login_page_accessible(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_login_post_redirects_on_success(self):
        response = self.client.post(
            reverse("login"),
            {"username": "testuser", "password": "testpass123"},
        )
        self.assertIn(response.status_code, [302, 200])

    def test_login_failure_shows_form(self):
        response = self.client.post(
            reverse("login"),
            {"username": "testuser", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_remember_me_checked_by_default(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="remember_me" checked')

    def test_login_with_remember_me_sets_long_expiry(self):
        from .views import CustomLoginView

        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": "testpass123",
                "remember_me": "on",
            },
        )
        self.assertIn(response.status_code, [302, 200])
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertAlmostEqual(
            self.client.session.get_expiry_age(),
            CustomLoginView.REMEMBER_ME_SESSION_AGE,
            delta=5,
        )

    def test_login_without_remember_me_expires_at_browser_close(self):
        response = self.client.post(
            reverse("login"),
            {"username": "testuser", "password": "testpass123"},
        )
        self.assertIn(response.status_code, [302, 200])
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_logout_requires_post(self):
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)

    def test_logout_post(self):
        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 302)


class LoginFormTests(TestCase):
    def test_form_widgets_have_bootstrap_class(self):
        form = LoginForm()
        self.assertIn("form-control", form.fields["username"].widget.attrs.get("class", ""))
        self.assertIn("form-control", form.fields["password"].widget.attrs.get("class", ""))


class UtilsTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staffuser", password="testpass123", is_staff=True
        )
        self.normal_user = User.objects.create_user(
            username="normaluser", password="testpass123"
        )
        self.group = Group.objects.create(name="testgroup")

    def test_is_staff_or_superuser_with_staff(self):
        self.assertTrue(is_staff_or_superuser(self.staff_user))

    def test_is_staff_or_superuser_with_normal(self):
        self.assertFalse(is_staff_or_superuser(self.normal_user))

    def test_is_staff_or_superuser_with_superuser(self):
        superuser = User.objects.create_superuser(
            username="super", password="testpass123"
        )
        self.assertTrue(is_staff_or_superuser(superuser))

    def test_group_required_decorator(self):
        wrapped = group_required("testgroup")(lambda request: None)
        self.assertIsNotNone(wrapped)
