FROM python:3.12-slim

# Без цього stdout буферизується при не-TTY виводі (docker compose exec
# без -it, docker compose logs) — короткі скрипти (напр.
# orchestration/run_job.py) можуть губити останні рядки виводу при
# виході процесу. logging (StreamHandler) сам робить flush після
# кожного запису й це не зачіпає — але plain print() ні.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sleep", "infinity"]
