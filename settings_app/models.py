from django.db import models


class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.CharField(max_length=300, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return f"{self.key}: {self.value}"

    @classmethod
    def get_setting(cls, key, default=""):
        setting, _ = cls.objects.get_or_create(key=key, defaults={"value": default})
        return setting.value

    @classmethod
    def set_setting(cls, key, value, description=""):
        setting, _ = cls.objects.get_or_create(
            key=key, defaults={"value": value, "description": description}
        )
        setting.value = value
        if description:
            setting.description = description
        setting.save()
