{% macro mute() %}
  {{ config(severity='warn') }}
{% endmacro %}
