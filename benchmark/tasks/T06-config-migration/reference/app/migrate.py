import copy


class UnsupportedVersion(Exception):
    pass


def _v1_to_v2(cfg):
    if "db_host" not in cfg or "db_port" not in cfg:
        raise ValueError("v1 needs db_host and db_port")
    out = {k: v for k, v in cfg.items() if k not in ("db_host", "db_port")}
    out["database"] = {"host": cfg["db_host"], "port": cfg["db_port"]}
    out["version"] = 2
    return out


def _v2_to_v3(cfg):
    out = dict(cfg)
    out["timeouts"] = {"connect": out.pop("connect_timeout", 10)}
    out["version"] = 3
    return out


def migrate(config):
    version = config.get("version")
    if type(version) is not int or version not in (1, 2, 3):
        raise UnsupportedVersion(version)
    cfg = copy.deepcopy(config)
    if version == 1:
        cfg = _v1_to_v2(cfg)
    if cfg["version"] == 2:
        cfg = _v2_to_v3(cfg)
    return cfg
