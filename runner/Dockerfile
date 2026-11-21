# PaySift Sandbox Container Image
# Used for isolated execution of untrusted model-generated payment handlers.

FROM python:3.12-slim

# Create runner directory structure
RUN mkdir -p /runner/contract

# Copy runner modules and contract fixtures
COPY runner/ /runner/runner/
COPY contract/events.py /runner/contract/events.py
COPY contract/schema.sql /runner/contract/schema.sql

# Set python path so runner modules resolve cleanly
ENV PYTHONPATH=/runner

# Working directory in disposable tmpfs
WORKDIR /tmp

# Non-root user 65534 (nobody:nogroup)
USER 65534:65534

# Default entrypoint
CMD ["python", "-m", "runner.worker"]
