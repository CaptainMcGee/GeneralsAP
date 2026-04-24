# Archipelago Patches

Store ordered patch files here for unavoidable edits to upstream-owned Archipelago files.

Guidelines:
- prefer a small number of focused patches
- name them with an order prefix, such as `010-world-loader.patch`
- keep additive GeneralsAP files in `../overlay` instead of patching them into upstream

Patches are applied in lexical order by `scripts/materialize_archipelago_vendor.py`.
