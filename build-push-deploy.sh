docker build . -t news-scraper-summarizer:latest --platform linux/amd64

docker tag news-scraper-summarizer:latest asia-east1-docker.pkg.dev/quantitative-trading-point/moni/news-scraper-summarizer:latest

docker push asia-east1-docker.pkg.dev/quantitative-trading-point/moni/news-scraper-summarizer:latest

gcloud run services update news-scraper-summarizer \
--image asia-east1-docker.pkg.dev/quantitative-trading-point/moni/news-scraper-summarizer:latest \
--region asia-east1
