import re
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

class App:
    def __init__(self, driverPath):
        self.receipeUrl = "https://www.10000recipe.com/recipe/list.html"
        self.driver = webdriver.Chrome(driverPath)
        self.currentReceipePage = 0
        self.ingredientDict = {}
        self.filePath = './results'

        self.debug = False

    def run(self):
        directory = createFolder(self.filePath)
        if directory is None:
            print("디렉토리 생성 실패로 인해 프로그램을 종료합니다.")
            return

        filePath = directory + "/" + datetime.now().strftime("%Y%M%d_%Hh%Mm%Ss") + ".json"
        result = []
        cnt = 0
        while True:
            self.nextReceipePage()
            try:
                self.driver.find_element(By.CSS_SELECTOR, '#contents_area_full > ul > div.result_none')    
                break
            except:
                pass

            receipeElementList = self.getReceipeListFromCurrentPage()
            for receipeElement in receipeElementList:
                receipe = self.getReceipe(receipeElement)
                result.append(receipe)

                # save
                with open(filePath, 'w', encoding='utf8') as jsonFile:
                    json.dump(result, jsonFile, indent="\t", ensure_ascii=False)

        

    def getReceipe(self, receipeElement):
        result = {}

        result['url'] = self.driver.current_url

        # open new tab
        temp = receipeElement.find_element(By.XPATH, './div[1]/a')
        temp.send_keys(Keys.CONTROL + "\n")
        self.driver.switch_to.window(self.driver.window_handles[1])

        # get title
        result['title'] = self.driver.find_element(By.XPATH, '//*[@id="contents_area"]/div[2]/h3').text

        if self.debug is True:
            print('레시피 제목 : ' + result['title'])
        
        # get ingredient
        ingredientContainer = self.driver.find_element(By.XPATH, '//*[@id="divConfirmedMaterialArea"]')
        result['ingredient'] = self.getIngredient(ingredientContainer)

        # get step
        result['step'] = []
        receipeContainer = self.driver.find_element(By.XPATH, '//*[@id="contents_area"]/div[12]')
        try:
            receipeContainer.find_element(By.CSS_SELECTOR, 'div.best_tit')
            receipeSteps = receipeContainer.find_elements(By.CSS_SELECTOR, 'div.view_step_cont')
            for receipeStep in receipeSteps:
                content = receipeStep.find_element(By.CSS_SELECTOR, 'div.media-body').text
                imgUrl = receipeStep.find_element(By.CSS_SELECTOR, 'div.media-right > img').get_attribute('src')
                result['step'].append([content, imgUrl])

                if self.debug is True:
                    print(content, imgUrl, end='\n\n')
        except:
            print('옛날 포맷이므로 패스')


        # close tab
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])
        return result

    def getIngredient(self, element):
        # get ingredient
        result = {}
        ingredientList = element.find_elements(By.TAG_NAME, 'ul')
        
        if self.debug is True:
            print('재료 >>')

        for i in ingredientList:
            subtitleElement = i.find_element(By.TAG_NAME, 'b')
            subtitle = re.sub('[\[\]]', '', subtitleElement.text)

            if self.debug is True:
                print('재료 그룹 : ' + subtitle)

            result[subtitle] = []

            subList = i.find_elements(By.TAG_NAME, 'li')
            for j in subList:
                try:
                    ingreDientElement = j.find_element(By.TAG_NAME, 'a')
                    ingredient = ingreDientElement.text
                    unit = j.find_element(By.TAG_NAME, 'span').text
                    result[subtitle].append([ingredient, unit])

                    # 재료 상세 정보 저장
                    ingredientDetail = self.getIngredientDetail(ingreDientElement)
                    self.ingredientDict[ingredientDetail['name']] = ingredientDetail
                except:
                    ingredient = j.text
                    unit = j.find_element(By.TAG_NAME, 'span').text
                    result[subtitle].append([ingredient, unit])

                if self.debug is True:
                    print(ingredient, unit)

        return result

    def getIngredientDetail(self, element):
        result = {}
        element.click()

        modal = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="materialViewModal"]'))
        )

        # get name
        try:
            result['name'] = modal.find_element(By.XPATH, '//*[@id="materialBody"]/div/div[1]/div[2]/b').text
        except: 
            result['name'] = modal.find_element(By.XPATH, '//*[@id="materialBody"]/div/div[1]/div/b').text

        if self.debug is True:
            print('재료 이름 : ' + result['name'])

        # get info
        if self.debug is True:
            print('재료 정보 >>')

        result['info'] = {}
        infos = modal.find_elements(By.XPATH, '//*[@id="materialBody"]/div/div[2]/table/tbody/tr')
        for info in infos:
            title = info.find_element(By.TAG_NAME, 'th').text
            value = info.find_element(By.TAG_NAME, 'td').text
            result['info'][title] = value

            if self.debug is True:
                print(title + " : " + value)

        # get efficacy (효능)
        if self.debug is True:
            print('효능 >>')
        result['efficacy'] = []
        try:
            efficacys = modal.find_elements(By.XPATH, '//*[@id="materialBody"]/div/dl[1]/dd/div/a')
            for efficacy in efficacys:
                result['efficacy'].append(efficacy.text)
                if self.debug is True:
                    print(efficacy.text)
        except:
            pass

        # close modal    
        modal.find_element(By.XPATH, '//*[@id="materialViewModal"]/div/div/div[1]/button').click()

        return result


    
    def goReceipePage(self, page: int):
        self.driver.get("%s?order=reco&page=%d" % (self.receipeUrl, page))
        
    def nextReceipePage(self):
        self.currentReceipePage += 1
        self.goReceipePage(self.currentReceipePage)

    def prevReceipePage(self):
        if self.currentReceipePage > 1:
            self.currentReceipePage -= 1
        self.goReceipePage(self.currentReceipePage)

    def getReceipeListFromCurrentPage(self):
        receipeListContainer = self.driver.find_element(By.XPATH, '//*[@id="contents_area_full"]/ul/ul')
        return receipeListContainer.find_elements(By.TAG_NAME, 'li')

def createFolder(path):
    import os

    try:
        if not os.path.exists(path):
            os.makedirs(path)
        return path
    except OSError:
        print('Error: Creating directory. ' + path)
        return None