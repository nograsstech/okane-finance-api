docker build . -t okane-finance-api:latest --platform linux/amd64 --no-cache

docker tag okane-finance-api:latest asia-east1-docker.pkg.dev/quantitative-trading-point/moni/okane-finance-api:latest

docker push asia-east1-docker.pkg.dev/quantitative-trading-point/moni/okane-finance-api:latest

gcloud run services add-iam-policy-binding okane-finance-api \
--member="allUsers" \
--role="roles/run.invoker" \
--region asia-east1

gcloud run services update okane-finance-api \
--image asia-east1-docker.pkg.dev/quantitative-trading-point/moni/okane-finance-api:latest \
--region asia-east1 
