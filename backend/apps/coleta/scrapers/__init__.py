"""
Scrapers específicos para diferentes fontes.

Cada scraper herda de ScraperBase e implementa lógica
específica para sua fonte de dados.
"""
from .cosit_scraper import CositScraper

__all__ = ['CositScraper']
