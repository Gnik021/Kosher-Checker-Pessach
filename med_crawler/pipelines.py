class MedCrawlerPipeline:
    def __init__(self):
        self.items = []

    def process_item(self, item, spider):
        self.items.append(item)
        return item
