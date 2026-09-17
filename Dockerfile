# The judged image. Built from the repository root, which is where the judges
# look -- and this is the only Dockerfile in the repository, so there is nothing
# for them to pick wrong.
#
#   docker build -t rca .
#   docker run --rm -e FEATHERLESS_API_KEY=... \
#     -v <bundle>:/data:ro -v <empty>:/out rca \
#     python run.py --dataset /data --queries /data/query.csv --out /out
#
# The container has no route out except the model endpoint during evaluation, so
# every dependency is installed at build time and nothing is fetched at runtime.
FROM python:3.12-slim

WORKDIR /app

# Dependencies first: this layer is cached across code edits.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run.py llm.py cost.py score.py ./
COPY agents/ ./agents/

# The judges run `python run.py ...` explicitly; this is the same thing for
# anyone who runs the image bare.
CMD ["python", "run.py", "--dataset", "/data", "--queries", "/data/query.csv", \
     "--out", "/out"]
