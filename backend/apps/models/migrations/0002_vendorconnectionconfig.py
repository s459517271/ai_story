from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('models', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='VendorConnectionConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vendor', models.CharField(max_length=64, verbose_name='厂商标识')),
                ('capability', models.CharField(choices=[('llm', 'LLM模型'), ('text2image', '文生图模型'), ('image2video', '图生视频模型'), ('image_edit', '图片编辑模型')], max_length=20, verbose_name='模型能力')),
                ('api_key', models.CharField(blank=True, default='', max_length=512, verbose_name='API密钥')),
                ('api_url', models.URLField(blank=True, default='', verbose_name='API地址')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vendor_connection_configs', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '厂商导入连接配置',
                'verbose_name_plural': '厂商导入连接配置',
                'db_table': 'vendor_connection_configs',
                'ordering': ['vendor', 'capability'],
            },
        ),
        migrations.AddConstraint(
            model_name='vendorconnectionconfig',
            constraint=models.UniqueConstraint(fields=('user', 'vendor', 'capability'), name='unique_vendor_connection_config_per_user'),
        ),
        migrations.AddIndex(
            model_name='vendorconnectionconfig',
            index=models.Index(fields=['user', 'vendor', 'capability'], name='vendor_con_user_id_954529_idx'),
        ),
    ]
