#!/usr/bin/env bash
# Запуск критика для fish-zone через Nous (deepseek-v4-flash-0731).
# Токен и base_url извлекаются из auth.json (не хардкодятся).
# DeepSeek-ключ исчерпан → используем Nous Portal (OpenAI-compat endpoint).
set -euo pipefail
cd "$(dirname "$0")"
unset PYTHONPATH

AUTH_JSON="$HOME/.hermes/profiles/fish/auth.json"
if [ ! -f "$AUTH_JSON" ]; then
  echo "ERROR: $AUTH_JSON не найден" >&2
  exit 3
fi

# Извлекаем access_token и inference_base_url первого nous-креденшела
NOUS_JSON=$(python3 -c "
import json,sys
d=json.load(open('$AUTH_JSON'))
pool=d.get('credential_pool',{}).get('nous',[])
if not pool:
    print('{}'); sys.exit(1)
p=pool[0]
print(json.dumps({'token':p.get('access_token',''), 'base':p.get('inference_base_url','https://inference-api.nousresearch.com/v1')}))
")
export NOUS_TOKEN=$(echo "$NOUS_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
export NOUS_BASE=$(echo "$NOUS_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['base'])")

if [ -z "$NOUS_TOKEN" ]; then
  echo "ERROR: нет nous access_token в auth.json" >&2
  exit 3
fi

# Критик использует OpenAI-формат. Направляем на Nous.
export DEEPSEEK_BASE_URL="$NOUS_BASE"
export DEEPSEEK_API_KEY="$NOUS_TOKEN"
export CRITIC_MODEL="deepseek/deepseek-v4-flash-0731"

.venv/bin/python tools/critic.py --file "$1" "${@:2}"
