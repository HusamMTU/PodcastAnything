# Infrastructure Notes

This directory contains the AWS CDK app for the `PodcastAnythingStack`.

## What This Stack Creates

- `ArtifactsBucket` (S3)
  - Bucket name comes from `MP_BUCKET`.
  - `auto_delete_objects=True` and `removal_policy=DESTROY` for clean teardown.
- `PythonDepsLayer` (Lambda Layer)
  - Built from `infra/layers/requirements.txt` using Docker during synth/deploy.
  - Includes article parsing dependencies used by Lambda handlers.
- `FetchArticleFn` (Lambda, Python 3.11)
  - Handler: `podcast_anything.handlers.fetch_article.handler`
- `RewriteScriptFn` (Lambda, Python 3.11)
  - Handler: `podcast_anything.handlers.rewrite_script.handler`
- `GenerateAudioFn` (Lambda, Python 3.11)
  - Handler: `podcast_anything.handlers.generate_audio.handler`
- `PipelineStateMachine` (Step Functions)
  - Sequence: `FetchArticleStep -> RewriteScriptStep -> GenerateAudioStep`
- `StartExecutionApiFn` (Lambda, Python 3.11)
  - Handler: `podcast_anything.api.handlers.start_execution_handler`
- `GetExecutionApiFn` (Lambda, Python 3.11)
  - Handler: `podcast_anything.api.handlers.get_execution_handler`
- `PodcastAnythingHttpApi` (API Gateway HTTP API)
  - Route: `POST /executions` -> `StartExecutionApiFn`
  - Route: `GET /executions` -> `GetExecutionApiFn`

## Permissions

- All three Lambdas get read/write access to `ArtifactsBucket`.
- `RewriteScriptFn` can call Bedrock:
  - `bedrock:InvokeModel`
  - `bedrock:InvokeModelWithResponseStream`
- `GenerateAudioFn` can call Polly:
  - `polly:SynthesizeSpeech`
- `StartExecutionApiFn` can start the deployed Step Functions state machine.
- `GetExecutionApiFn` can call `states:DescribeExecution`.

## Required Environment Variables (at synth/deploy time)

- `MP_BUCKET`
- `BEDROCK_MODEL_ID`

Optional:
- `POLLY_VOICE_ID` (default: `Joanna`)
- `AWS_REGION` (default used by app: `us-east-1`)

## Stack Outputs

- `ArtifactsBucketName`
- `FetchArticleFnName`
- `RewriteScriptFnName`
- `GenerateAudioFnName`
- `PipelineStateMachineArn`
- `StartExecutionApiFnName`
- `GetExecutionApiFnName`
- `HttpApiUrl`

`scripts/start_execution.py` can look up `HttpApiUrl` (default mode) or `PipelineStateMachineArn` (`--mode direct`) from these outputs.

## Architecture Sketch

```mermaid
flowchart LR
  subgraph CLIENT[Client Side]
    U[User]
    SE[scripts/start_execution.py]
    CC["Local caption fetch<br/>(YouTube only, in CLI)"]
    U --> SE
    SE -->|YouTube URL| CC
  end

  subgraph API[HTTP API]
    APIGW[API Gateway HTTP API]
    POSTX[POST /executions]
    GETX[GET /executions]
    SAE[Lambda: StartExecutionApiFn]
    GES[Lambda: GetExecutionApiFn]
    APIGW --> POSTX --> SAE
    APIGW --> GETX --> GES
  end

  SE -->|Article URL| APIGW
  CC -->|source_url + transcript_text| APIGW
  U -->|status request| APIGW
  APIGW -->|status response| U

  SAE --> SFN["Step Functions<br/>PipelineStateMachine"]
  GES -->|DescribeExecution| SFN
  SFN -->|execution status| GES

  subgraph PIPE[State Machine Execution Order]
    F["FetchArticleStep<br/>Lambda: FetchArticleFn<br/>(fetch article or persist provided transcript)"]
    R["RewriteScriptStep<br/>Lambda: RewriteScriptFn"]
    G["GenerateAudioStep<br/>Lambda: GenerateAudioFn"]
    F -->|event + article_s3_key| R
    R -->|event + script_s3_key| G
  end

  SFN -->|invokes first step| F
  F -->|write source.txt| S3[(S3 ArtifactsBucket)]
  S3 -->|read source.txt| R
  R -->|write script.txt + script.json| S3
  R -->|InvokeModel| BR[Bedrock Runtime]
  S3 -->|read script.txt| G
  G -->|write audio.mp3| S3
  G -->|SynthesizeSpeech| P[Amazon Polly]
```

Execution summary:
- Input event starts in Step Functions with `job_id` and `source_url`.
- Steps run in strict order: `fetch -> rewrite -> generate`.
- Each step adds new keys to the event payload and passes it to the next step.
- Final artifacts are stored under `jobs/<job_id>/` in S3.
