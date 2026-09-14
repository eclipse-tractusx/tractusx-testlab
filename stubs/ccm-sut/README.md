<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This program and the accompanying materials are made available under the
 terms of the Apache License, Version 2.0 which is available at
 https://www.apache.org/licenses/LICENSE-2.0.

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 License for the specific language governing permissions and limitations
 under the License.

 SPDX-License-Identifier: Apache-2.0
-->
<!-- This documentation was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# CCM SUT Stub

Disposable FastAPI application that simulates an EDC connector and CCMAPI-compliant service for Certificate Management (CX-0135) TCK tests. Run the full test suite locally without real infrastructure.

## How It Works

The stub replaces two real components in a single process on port 8090:

- **EDC Connector** — DSP catalog discovery, contract negotiation, transfer initiation, and EDR issuance. All negotiations auto-finalize and EDRs point back to `localhost:8090`.
- **CCMAPI Service** — Certificate request, push, available, and notification endpoints. Responses follow the CX-0135 v3.1.0 `{header, content}` envelope format.

### DSP protocol flow

Every request follows the standard EDC sequence, with all steps auto-succeeding:

1. **Catalog** → returns 2 datasets: `CCMAPI` (offer `ccm-offer-001`) and `Submodel` (BusinessPartnerCertificate v3.1.0)
2. **Negotiate** → auto-finalizes, returns agreement ID
3. **Transfer** → returns transfer ID
4. **EDR** → returns `{endpoint: localhost:8090, authCode: edr-token-xxx}`

### Callback behavior

After certain requests, the stub sends async HTTP callbacks to the TestLab mock server (`http://localhost:8100`):

| Trigger Endpoint | Callback Target | Delay | Payload Summary |
|-----------------|----------------|-------|-----------------|
| `POST /companycertificate/request` | `/companycertificate/status` | 10s | `{certificateStatus: RECEIVED, documentId: doc-xxx}` |
| `POST /companycertificate/push` | `/companycertificate/status` | 1s | `{certificateStatus: RECEIVED}` |
| `POST /companycertificate/notification/receive` | `/companycertificate/notification/receive` | 1s | Notification acknowledgment |
| `POST /` (dataplane root) | `/companycertificate/notification/receive` | 1s | Notification acknowledgment |

### Startup consumer simulation

On startup, the stub waits 20 seconds then sends `GET {TESTLAB_CALLBACK_URL}/api/v1/companycertificate` to simulate a real SUT discovering and pulling TestLab's exposed asset.

## Endpoints

| Method | Path | Response |
|--------|------|----------|
| POST | `/api/v1/dsp/catalog/request` | DSP catalog with CCMAPI + Submodel datasets |
| POST | `/api/v1/dsp/negotiations/initial` | Auto-finalized agreement |
| POST | `/api/v1/dsp/negotiations/request` | Auto-finalized agreement (alias) |
| GET | `/api/v1/dsp/negotiations/{id}` | FINALIZED status |
| POST | `/management/v3/transferprocesses` | Transfer ID |
| GET | `/management/v3/edrs/{id}/dataaddress` | EDR with bearer token |
| POST | `/companycertificate/request` | `{requestStatus: COMPLETED}` + 10s callback |
| POST | `/companycertificate/request?reject=true` | `{requestStatus: REJECTED}` (no callback) |
| POST | `/companycertificate/push` | OK + 1s feedback callback |
| POST | `/companycertificate/available` | OK |
| POST | `/companycertificate/notification/receive` | OK + 1s ack callback |
| GET | `/companycertificate/{document_id}` | BusinessPartnerCertificate v3.1.0 payload |
| POST | `/` | OK + 1s notification ack (dataplane root) |
| GET | `/health` | `{status: healthy}` |

Management API routes are also available under `/api/v1/dsp/management/v3/` for SDK compatibility (see `management.py`).

## Run

```bash
cd stubs/ccm-sut
pip install fastapi uvicorn httpx
python app.py
```

Or with hot-reload:

```bash
uvicorn app:app --host 0.0.0.0 --port 8090 --reload
```

## Docker

Build the image:

```bash
docker build -t ccm-sut-stub stubs/ccm-sut/
```

Run the container:

```bash
docker run -p 8090:8090 \
  -e TESTLAB_CALLBACK_URL=http://host.docker.internal:8100 \
  -e PROVIDER_BPN=BPNL000000000001 \
  -e CONSUMER_BPN=BPNL000000000002 \
  -e CALLBACK_DELAY_SECONDS=10 \
  ccm-sut-stub
```

## Helm

Install with Helm:

```bash
helm install ccm-sut stubs/ccm-sut/charts/ccm-sut-stub/
```

Override values:

```bash
helm install ccm-sut stubs/ccm-sut/charts/ccm-sut-stub/ \
  --set config.testlabMockBaseUrl=http://testlab:8100 \
  --set config.providerBpn=BPNL000000000001 \
  --set config.callbackDelaySeconds=5
```

See [values.yaml](charts/ccm-sut-stub/values.yaml) for all configurable parameters.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TESTLAB_CALLBACK_URL` | `http://localhost:8100` | TestLab mock server URL for callbacks |
| `PROVIDER_BPN` | `BPNL000000000001` | Stub's Business Partner Number |
| `CONSUMER_BPN` | `BPNL000000000002` | TestLab's Business Partner Number |
| `CALLBACK_DELAY_SECONDS` | `10` | Delay before sending async callbacks |
| `STUB_PORT` | `8090` | Port the stub listens on |
| `STUB_BASE_URL` | `http://localhost:8090` | Base URL returned in EDR data addresses |
| `DSP_FEEDBACK_URL` | `http://localhost:8090/api/v1/dsp` | DSP feedback URL in response headers |

## Configuration

The `run-config.yaml` file supplies runtime variables to the test suite:

| Variable | Value | Purpose |
|----------|-------|---------|
| `provider_address` | `http://localhost:8090/api/v1/dsp` | Stub's DSP endpoint |
| `provider_bpn` | `BPNL000000000001` | Stub's Business Partner Number |
| `consumer_bpn` | `BPNL000000000002` | TestLab's Business Partner Number |
| `certificate_type` | `iso9001` | Certificate type to request |
| `location_bpns` | `BPNS000000000001` | Site needing the certificate |
| `testlab_mock_base_url` | `http://localhost:8100` | TestLab mock server (callback target) |
| `testlab_management_url` | `http://localhost:8090/api/v1/dsp` | TestLab EDC management API |
| `testlab_dsp_url` | `http://localhost:8090/api/v1/dsp` | TestLab DSP endpoint |
| `sut_response_timeout` | `60` | Max seconds to wait for callbacks |

Run the test suite with:

```bash
testlab run docs/examples/certificate-management-v2/raw/index.yaml \
  --config stubs/ccm-sut/run-config.yaml
```

## Adapting for Your Tests

### Change callback timing

Edit the delay constants in `app.py`:

```python
CALLBACK_DELAY_SECONDS = 10  # change to your preferred delay
```

Async callback helpers (`_send_callback`, `_send_notification_ack`, `_send_push_feedback`) each have their own `asyncio.sleep()` call.

### Add new endpoints

1. Add a route handler in `app.py`
2. Create the response builder in `responses.py`
3. For callbacks, follow the `asyncio.create_task(_send_*)` pattern

### Modify response payloads

Edit `responses.py` to change certificate data, status codes, or header values. The `CERTIFICATE_PAYLOAD` dict contains the BusinessPartnerCertificate v3.1.0 response template.

### Switch to a real SUT

Replace `run-config.yaml` values with your real EDC and BPN details:

```yaml
variables:
  provider_address: "https://your-edc:8282/api/v1/dsp"
  provider_bpn: "BPNL00000003AZQP"
  consumer_bpn: "BPNL00000001SQRN"
  # ... remaining variables for your environment
```

## File Structure

| File | Purpose |
|------|---------|
| `app.py` | FastAPI application with DSP, CCMAPI, and callback logic |
| `responses.py` | CX-0135 compliant response builders and payload templates |
| `management.py` | Management API routes under `/api/v1/dsp/management/v3/` |
| `run-config.yaml` | Runtime variable overrides for the test suite |

Edit `TESTLAB_CALLBACK_URL` in `app.py` if your TestLab server runs on a different address.

## Config

`config.env` contains the variables the TestLab runner needs to connect to this stub.
