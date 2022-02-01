{% if message.guild -%}
{{ message.channel.mention }} ({{ message.guild.name }}) {{ message.author.mention }}: {{ message.clean_content }}
{% else %}
{{ message.author.mention }}: {{ message.clean_content }}
{% endif %}

{% if message.attachments -%}
**Attachments:**
{% for attachment in message.attachments -%}
{{ attachment.proxy_url }}
{% endfor -%}
{% endif -%}
