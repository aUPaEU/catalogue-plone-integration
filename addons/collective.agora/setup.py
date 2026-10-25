from setuptools import find_namespace_packages, setup

setup(
    name="collective.agora",
    version="1.0.0",
    description="Agora templates for Plone Classic TinyMCE",
    package_dir={"": "src"},
    packages=find_namespace_packages("src"),
    include_package_data=True,
    install_requires=["setuptools", "Products.CMFPlone", "plone.registry", "plone.app.registry", "requests"],
    entry_points={"z3c.autoinclude.plugin": ["target = plone"]},
)
