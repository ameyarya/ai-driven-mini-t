"""Local-only adapter inference for the offline playground, without hardware."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import hashlib
from pathlib import Path
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parent
LOCK=threading.Lock()
MODEL_NAME='qwen3-vl:4b-rook-lora-mlx'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8767)
    args=parser.parse_args()
    from mlx_vlm import load,generate
    from mlx_vlm.prompt_utils import apply_chat_template
    from mlx_vlm.structured import build_json_schema_logits_processor
    import mlx.core as mx
    model,processor=load(str(ROOT/'tools/qwen3-vl-4b-mlx'),
        adapter_path=str(ROOT/'playground-data/planner-training/adapter-v1'))

    class Handler(BaseHTTPRequestHandler):
        def reply(self,status,body):
            payload=json.dumps(body).encode();self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(payload)));self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self.reply(200,dict(ready=True,model=MODEL_NAME,motor_commands_sent=False)) if self.path=='/health' else self.reply(404,dict(error='Not found'))

        def do_POST(self):
            if self.path!='/api/chat':return self.reply(404,dict(error='Not found'))
            if self.headers.get('Origin'):return self.reply(403,dict(error='Use the local playground server'))
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<4_000_000:raise ValueError('Invalid body size')
                body=json.loads(self.rfile.read(length))
                message=body['messages'][0]
                image=base64.b64decode(message['images'][0],validate=True)
                output=ROOT/'playground-data/mlx-inference'/uuid.uuid4().hex
                output.mkdir(parents=True);image_path=output/'input.jpg';image_path.write_bytes(image)
                with LOCK:
                    prompt=apply_chat_template(processor,model.config,message['content'],num_images=1)
                    constraint=build_json_schema_logits_processor(processor.tokenizer,body['format'])
                    start=time.monotonic()
                    response=generate(model,processor,prompt,image=[str(image_path)],max_tokens=160,
                        temperature=0,verbose=False,logits_processors=[constraint])
                    result=dict(model=MODEL_NAME,input_sha256=hashlib.sha256(image).hexdigest(),message=dict(role='assistant',content=response.text),
                        done=True,done_reason='length' if response.generation_tokens>=160 else 'stop',
                        eval_duration=int((time.monotonic()-start)*1e9),prompt_eval_duration=0)
                    (output/'response.json').write_text(json.dumps(result,indent=2)+'\n')
                    mx.clear_cache()
                self.reply(200,result)
            except (ValueError,KeyError,TypeError,OSError,RuntimeError) as error:
                self.reply(400,dict(error=str(error)))

    # MLX streams are thread-local; inference stays on the model-loading thread.
    server=HTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Fine-tuned local planner: http://127.0.0.1:{args.port}',flush=True)
    server.serve_forever()


if __name__=='__main__':main()
