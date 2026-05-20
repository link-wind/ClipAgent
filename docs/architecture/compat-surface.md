# Compat Surface

当前 `backend.services.*` 不再是开放式实现目录，当前 frozen compat surface 已收缩为 0。

现阶段不再保留带明确豁免理由的 `backend.services.*` 兼容入口；如后续确有新增 compat 需求，必须先补 architecture guard 和文档，再引入最小范围的临时白名单。
