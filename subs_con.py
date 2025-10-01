from singbox_converter import SingBoxConverter

converter = SingBoxConverter(
    providers_config="providers.json",
    template="template.json",
    fetch_sub_ua="clash.meta",
    # fetch_sub_fallback_ua="clash",
    # export_config_folder="",
    # export_config_name="my_config.json",
    # auto_fix_empty_outbound=True,
)

print(converter.singbox_config)

converter.export_config(
    path="main",
    # nodes_only=True
)
