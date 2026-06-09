import uvicorn


def main() -> None:
    uvicorn.run("vectorforge_v1.exp_designer.trad_ml.autogluon.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
