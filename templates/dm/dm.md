{{ message.author.mention }}: {{ message.clean_content }}

{% if message.attachments -%}
**Attachments:**
{% for attachment in message.attachments -%}
{{ attachment.proxy_url }}
{% endfor -%}
{% endif -%}
