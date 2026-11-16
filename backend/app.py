import argparse
import shutil
import socket
import sys
from pathlib import Path

from flask import Flask, jsonify

BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _requested_data_dir():
    """--data-dir 必须在 config 首次导入前生效，因此先于下方导入解析一次。"""
    if __name__ != "__main__":
        return None
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--data-dir")
    known, _ = parser.parse_known_args()
    return known.data_dir


def _isolate_data_dir(value):
    import config

    root = (BACKEND.parent / value).resolve()
    local_root = config.LOCAL_ENVIRONMENT_ROOT.resolve()
    if not root.is_relative_to(local_root) or root == local_root:
        sys.exit("--data-dir 必须指向 .local 内的独立数据目录。")
    config.PROJECT_ROOT = root
    config.DATA_ROOT = root / "backend/data"
    config.USER_ROOT = config.DATA_ROOT / "users"
    config.FIGURE_ROOT = root / "figures"
    config.ENV_DEFAULTS["FOREST_VAULT_KEY_FILE"] = str(root / config.LOCAL_VAULT_KEY_FILE)
    return root


DATA_DIR = _requested_data_dir()
ISOLATED_ROOT = _isolate_data_dir(DATA_DIR) if DATA_DIR else None

# isort: off
from agent.api.agent_api import agent_api  # noqa: E402
from agent.api.ai_api import ai_api  # noqa: E402
from agent.api.auth_api import auth_api  # noqa: E402
from config import PROJECT_ROOT, SERVER_HOST, SERVER_PORT, environment  # noqa: E402
from agent.api.conversations_api import conversations_api  # noqa: E402
from agent.api.learning_exploration_api import learning_exploration_api  # noqa: E402
from agent.api.study_api import study_api  # noqa: E402
from agent.api.experiments_api import experiments_api  # noqa: E402
from agent.api.files_api import files_api  # noqa: E402
from agent.api.speech_api import speech_api  # noqa: E402
from agent.api.attachments_api import attachments_api  # noqa: E402
from agent.figure_scope import migrate_legacy  # noqa: E402
from agent.api.figures_api import figures_api, figures_root  # noqa: E402
from agent.api.rag_api import rag_api  # noqa: E402

# isort: on

ALLOWED_ORIGINS = set()
ALLOW_ANY_ORIGIN = False


def local_names():
    names = {"127.0.0.1", "localhost", "::1"}
    try:
        host = socket.gethostname()
        names.add(host.lower())
        names.add((host + ".local").lower())
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            names.add(info[4][0])
    except (OSError, socket.gaierror):
        pass
    return names


LOCAL_NAMES = local_names()


def origin_allowed(origin):
    if origin is None:
        return True
    configured = {
        value.strip() for value in environment("FOREST_ALLOWED_ORIGINS").split(",") if value.strip()
    }
    if origin in configured or origin in ALLOWED_ORIGINS:
        return True
    if environment("FOREST_ENV") == "production":
        return False
    if ALLOW_ANY_ORIGIN:
        return True
    from urllib.parse import urlsplit

    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    return (parsed.hostname or "").lower() in LOCAL_NAMES


def create_app():
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False
    migrate_legacy(PROJECT_ROOT, PROJECT_ROOT / "backend" / "data" / "sessions")
    app.json.ensure_ascii = False

    app.register_blueprint(auth_api, url_prefix="/api/auth")
    app.register_blueprint(agent_api, url_prefix="/api/agent")
    app.register_blueprint(conversations_api, url_prefix="/api/conversations")
    app.register_blueprint(learning_exploration_api, url_prefix="/api/learning-exploration")
    app.register_blueprint(study_api, url_prefix="/api/study")
    app.register_blueprint(experiments_api, url_prefix="/api/experiments")
    app.register_blueprint(files_api, url_prefix="/api/files")
    app.register_blueprint(speech_api, url_prefix="/api/speech")
    app.register_blueprint(attachments_api, url_prefix="/api/attachments")
    app.register_blueprint(rag_api, url_prefix="/api/rag")
    app.register_blueprint(figures_api, url_prefix="/api/figures")
    app.register_blueprint(figures_root, url_prefix="/api/figures")
    app.register_blueprint(ai_api, url_prefix="/api/ai")
    from agent.api.providers_api import providers_api

    app.register_blueprint(providers_api, url_prefix="/api/providers")

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "service": "forest-learning-lab",
                "study_schema_version": 2,
                "role": "backend",
                "framework": "flask",
                "frontend": "separate",
                "chat_format": "openai-chat-completions",
                "agent": "/api/agent/chat",
                "tool_execution": "server",
            }
        )

    @app.before_request
    def guard_origin():
        from flask import request

        if not request.path.startswith("/api/"):
            return None
        origin = request.headers.get("Origin")
        if origin_allowed(origin):
            return None
        return jsonify(
            {
                "error": "来源不被允许：请从本机或局域网前端页面发起请求，"
                "或用 --allow-origin 指定前端来源。"
            }
        ), 403

    @app.after_request
    def allow_cors(response):
        from flask import request

        origin = request.headers.get("Origin")
        if origin and origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, X-DSH-Blocking, Authorization, X-Auth-Token, X-Study-Owner, X-Forest-Request"
            )
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "接口不存在。"}), 404

    @app.errorhandler(405)
    def not_allowed(_error):
        return jsonify({"error": "方法不允许。"}), 405

    @app.errorhandler(500)
    def server_error(error):
        return jsonify({"error": "服务内部错误，请联系管理员检查服务日志。"}), 500

    from agent.security import install

    install(app)
    return app


def seed_samples(root):
    """把仓库自带的示例 CSV 播种到运行目录，已有文件不覆盖。"""
    source_dir = BACKEND.parent / "data"
    if not source_dir.is_dir() or Path(root) == BACKEND.parent:
        return
    destination_dir = Path(root) / "data"
    for source in source_dir.glob("*.csv"):
        destination = destination_dir / source.name
        if destination.exists():
            continue
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def lan_addresses():
    found = []
    for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
        address = info[4][0]
        if address not in found and not address.startswith(("127.", "169.254.")):
            found.append(address)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
        if address not in found and not address.startswith(("127.", "169.254.")):
            found.insert(0, address)
    except OSError:
        pass
    finally:
        sock.close()
    return found


def print_urls(host, port, frontend_port):
    print(f"后端接口（本机）：http://127.0.0.1:{port}/api/health", flush=True)
    if host in ("0.0.0.0", "::"):
        for address in lan_addresses():
            print(f"后端接口（局域网）：http://{address}:{port}/api/health", flush=True)
            if frontend_port:
                print(f"前端页面（局域网）：http://{address}:{frontend_port}/", flush=True)
        print("已绑定所有网卡；若被系统防火墙拦截，需要为 Python 放行入站连接。", flush=True)
    else:
        print("当前只绑定本机回环地址；如需局域网访问，请加 --host 0.0.0.0。", flush=True)
    if frontend_port:
        print(f"前端页面用 Vite 启动：npm run dev（端口 {frontend_port}）。", flush=True)
    print("后端只提供接口，不托管静态文件。", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=SERVER_PORT)
    parser.add_argument("--host", default=SERVER_HOST, help="绑定地址；局域网访问用 0.0.0.0")
    parser.add_argument(
        "--allow-origin", action="append", default=[], help="额外允许的前端来源，可重复"
    )
    parser.add_argument(
        "--allow-any-origin", action="store_true", help="允许任意来源（仅本地调试）"
    )
    parser.add_argument("--frontend-port", type=int, help="打印指定前端端口的地址")
    parser.add_argument(
        "--data-dir",
        help="改用 .local 内的独立数据目录，便于隔离预览；同时按端口区分登录 Cookie",
    )
    args = parser.parse_args()
    ALLOWED_ORIGINS.update(args.allow_origin)
    ALLOW_ANY_ORIGIN = args.allow_any_origin
    seed_samples(PROJECT_ROOT)
    application = create_app()
    if ISOLATED_ROOT is not None:
        application.config["AUTH_COOKIE"] = "forest_message_actions_preview_" + str(args.port)
    print_urls(args.host, args.port, args.frontend_port)
    application.run(host=args.host, port=args.port, threaded=True, debug=False, use_reloader=False)
